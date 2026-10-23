"""World Model, el motor de estado del mundo de Meterless (engines/world-model), implementado para IO (Paso 13).

Para qué lo usa IO: llevar un registro canónico de las COSAS que el agente vio en los datos (disputas,
clientes, pedidos, envíos, transportistas, regiones), de dónde salió cada una y qué se sabe de ellas.
Cumple tres funciones:

  1. Anclaje (continuity anchors, AGENTS.md §5.3). Antes de aceptar una conclusión, el Evaluador le
     pregunta al World Model si cada disputa, transportista y región que nombra salió en una consulta de
     ESTA corrida. Si el modelo nombra algo que solo conoce de memoria (H-MEM) o que inventó, se le
     devuelve. H-MEM da pistas; el World Model exige que estén ancladas a evidencia.
  2. Resolución de ids (ingest-pipeline, etapa resolve). Si una consulta no devuelve filas porque el
     modelo escribió mal un id (du_…jgujrs en vez de du_…jgujrS), el World Model reconoce el id canónico
     y se lo sugiere en vez de dejarlo buscando.
  3. Auditoría. Cada cosa tiene un id estable y cada escritura deja un evento con su procedencia (qué
     corrida, qué evidencia E#, checksum de las filas), así que se puede reconstruir de dónde salió todo.

Qué tomamos del plano (AGENTS.md y docs/ de engines/world-model):
  - Las formas Entity, Context, Relationship, Fact, Provenance y Event, con schemaVersion.
  - Ids estables y derivados del contenido: `disputa:io:du_…` para lo que tiene id externo, y
    `ent_<sha256[:16]>` sobre el nombre normalizado para transportistas y regiones.
  - Un registro de eventos de solo agregar; el estado es un fold sobre los eventos. Una escritura sin
    procedencia se rechaza en el borde.
  - Ingesta idempotente: volver a ingerir la misma evidencia produce cero eventos nuevos.
  - Vistas que se reconstruyen desde los eventos: grafo (vecinos), snapshot (qué se vio en un contexto)
    y búsqueda por nombre para resolver.
Lo que no implementamos (no hace falta para IO en el hackathon): el control plane para operadores,
la resolución probabilística por embeddings y las colas de enriquecimiento.

Todo pasa por MundoAgente (el adaptador), con tiempo límite y respaldo: si el World Model está apagado
(AGENTE_MUNDO=false), tarda más de AGENTE_MUNDO_TIMEOUT_S o falla, el agente sigue sin él (sin
anclaje ni resolución de ids) y la traza lo dice. Los eventos viven en <AGENTE_MUNDO_DIR>/eventos.jsonl.
"""

import hashlib
import json
import re
import shutil
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TiempoAgotado
from datetime import datetime, timezone
from pathlib import Path

from agente.traza import Cronometro

VERSION_ESQUEMA = 1

# Columnas de canonico.* que identifican una cosa (entidad). Las de id externo usan el id de io-engine;
# transportista y región no tienen id, así que se identifican por su nombre normalizado.
CLAVE_EXTERNA = {"disputa_id": "disputa", "pago_id": "pago", "pedido_id": "pedido", "envio_id": "envio",
                 "cliente_id": "cliente"}
CLAVE_NOMBRE = {"transportista": "transportista", "region": "region"}
# De qué entidad es un hecho de la fila: de la más específica que aparezca.
PRIORIDAD = ["disputa", "envio", "pago", "pedido", "cliente", "transportista", "region"]
# Relaciones que se leen de una misma fila (desde, tipo, hacia).
RELACIONES = [("disputa", "de_pedido", "pedido"), ("disputa", "de_cliente", "cliente"),
              ("disputa", "de_pago", "pago"), ("disputa", "enviada_por", "transportista"),
              ("disputa", "en_region", "region"), ("envio", "de_pedido", "pedido"),
              ("envio", "enviado_por", "transportista"), ("transportista", "opera_en", "region")]
# Lo que el Evaluador exige anclar si aparece en la conclusión o la recomendación.
TIPOS_ANCLADOS = ("disputa", "transportista", "region")
ID_DISPUTA = re.compile(r"\bdu_[A-Za-z0-9]+\b")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def normalizar_nombre(nombre: str) -> str:
    """lowercase → NFKD → sin marcas → espacios colapsados → trim (docs/stable-ids.md)."""
    texto = unicodedata.normalize("NFKD", str(nombre).lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.split())


def _hash(*partes) -> str:
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def id_entidad(tipo: str, clave_externa: str | None = None, nombre: str | None = None) -> str:
    if clave_externa:
        return f"{tipo}:io:{clave_externa}"
    return f"ent_{hashlib.sha256(f'{tipo}:{normalizar_nombre(nombre)}'.encode()).hexdigest()[:16]}"


def id_contexto(tipo: str, clave: str, padre: str | None = None) -> str:
    return f"{tipo}:io:{clave}" if not padre else f"ctx_{_hash(tipo, clave, padre)[:16]}"


class SinProcedencia(ValueError):
    pass


class WorldModel:
    """Almacén canónico: registro de eventos de solo agregar + estado plegado + vistas."""

    def __init__(self, carpeta: Path):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.ruta = self.carpeta / "eventos.jsonl"
        self.entidades: dict[str, dict] = {}
        self.contextos: dict[str, dict] = {}
        self.relaciones: dict[str, dict] = {}
        self.hechos: dict[str, dict] = {}
        self.vistos: dict[str, set[str]] = {}    # contexto -> entidades que aparecieron en él (vista snapshot)
        self.vecinos: dict[str, set[str]] = {}   # entidad -> entidades relacionadas (vista grafo)
        self.claves: set[str] = set()            # claves de deduplicación de los eventos ya escritos
        self.ultimo_id = 0
        self._por_escribir: list[str] = []       # eventos nuevos aún no bajados a disco (se escriben en lote)
        if self.ruta.exists():
            for linea in self.ruta.read_text(encoding="utf-8").splitlines():
                if linea.strip():
                    self._plegar(json.loads(linea))

    # -- el registro ----------------------------------------------------------------------
    def _agregar(self, tipo: str, carga: dict) -> bool:
        """Escribe un evento si no existe ya uno igual (misma clave). Devuelve True si era nuevo."""
        fuente = carga.get("source")
        if not fuente or not fuente.get("kind"):
            raise SinProcedencia(f"World Model: '{tipo}' sin procedencia se rechaza en el borde")
        clave = _hash(tipo, {k: v for k, v in carga.items() if k != "source"},
                      {k: v for k, v in fuente.items() if k != "at"})
        if clave in self.claves:
            return False
        self.ultimo_id += 1
        evento = {"id": self.ultimo_id, "kind": tipo, "payload": carga, "schemaVersion": VERSION_ESQUEMA,
                  "at": _ahora(), "dedupeKey": clave}
        self._por_escribir.append(json.dumps(evento, ensure_ascii=False, default=str))
        self._plegar(evento)
        return True

    def guardar(self):
        """Baja a disco los eventos nuevos, en un solo append (el registro nunca se reescribe)."""
        if self._por_escribir:
            with open(self.ruta, "a", encoding="utf-8") as f:
                f.write("\n".join(self._por_escribir) + "\n")
            self._por_escribir = []

    def _plegar(self, evento: dict):
        """El estado es un fold sobre los eventos (read-your-writes: se aplica al escribir)."""
        self.ultimo_id = max(self.ultimo_id, evento["id"])
        self.claves.add(evento["dedupeKey"])
        p, tipo = evento["payload"], evento["kind"]
        if tipo == "upsertEntity":
            actual = self.entidades.setdefault(p["id"], {**p, "attrs": {}, "createdAt": evento["at"]})
            actual["attrs"].update(p["attrs"])
            actual["updatedAt"] = evento["at"]
        elif tipo == "upsertContext":
            self.contextos.setdefault(p["id"], {**p, "attrs": {}})["attrs"].update(p["attrs"])
        elif tipo == "relate":
            self.relaciones[p["id"]] = p
            self.vecinos.setdefault(p["from"], set()).add(p["to"])
            self.vecinos.setdefault(p["to"], set()).add(p["from"])
        elif tipo == "assertFact":
            self.hechos[p["id"]] = p
            if p.get("context"):
                self.vistos.setdefault(p["context"], set()).add(p["about"])

    # -- primitivas de escritura ----------------------------------------------------------
    def upsert_entity(self, tipo, fuente, clave_externa=None, nombre=None, attrs=None) -> tuple[str, bool]:
        eid = id_entidad(tipo, clave_externa, nombre)
        attrs = {**(attrs or {}), **({"nombre": nombre} if nombre else {}),
                 **({"clave_externa": clave_externa} if clave_externa else {})}
        return eid, self._agregar("upsertEntity", {"id": eid, "type": tipo, "attrs": attrs, "source": fuente})

    def upsert_context(self, tipo, clave, fuente, padre=None, attrs=None) -> tuple[str, bool]:
        cid = id_contexto(tipo, clave, padre)
        return cid, self._agregar("upsertContext", {"id": cid, "type": tipo, "parent": padre,
                                                   "attrs": attrs or {}, "source": fuente})

    def relate(self, desde, tipo, hacia, fuente, contexto=None) -> tuple[str, bool]:
        rid = f"rel_{_hash(desde, tipo, hacia, contexto)[:16]}"
        return rid, self._agregar("relate", {"id": rid, "from": desde, "type": tipo, "to": hacia,
                                             "context": contexto, "source": fuente})

    def assert_fact(self, sobre, predicado, valor, fuente, contexto=None, confianza=1.0,
                    calificadores=None) -> tuple[str, bool]:
        fid = f"fact_{_hash(sobre, predicado, valor, contexto, calificadores)[:16]}"
        return fid, self._agregar("assertFact", {"id": fid, "about": sobre, "predicate": predicado, "value": valor,
                                                 "confidence": confianza, "context": contexto,
                                                 "qualifiers": calificadores or {}, "source": fuente})

    # -- vistas ---------------------------------------------------------------------------
    def vistos_en(self, contexto: str) -> set[str]:
        return self.vistos.get(contexto, set())

    def de_tipo(self, tipo: str) -> list[dict]:
        return [e for e in self.entidades.values() if e["type"] == tipo]

    def donde_se_vio(self, entidad: str, contexto: str) -> list[str]:
        """Las evidencias (E#) de esa corrida en las que apareció la entidad."""
        refs = {h["value"] for h in self.hechos.values()
                if h["about"] == entidad and h["context"] == contexto and h["predicate"] == "visto_en"}
        return sorted(refs, key=lambda r: int(r[1:]) if r[1:].isdigit() else 0)


# -- ingesta (normalizar → resolver → validar → agregar → proyectar) --------------------------
def ingerir_filas(mundo: WorldModel, filas: list[dict], contexto: str, fuente: dict) -> dict:
    """Pasa las filas de una consulta al World Model. Idempotente: las mismas filas no agregan nada."""
    nuevos = repetidos = 0
    entidades_vistas = set()

    def contar(nuevo):
        nonlocal nuevos, repetidos
        nuevos, repetidos = nuevos + bool(nuevo), repetidos + (not nuevo)

    for fila in filas:
        en_fila: dict[str, str] = {}
        for col, tipo in CLAVE_EXTERNA.items():
            if fila.get(col) not in (None, ""):
                eid, n = mundo.upsert_entity(tipo, fuente, clave_externa=str(fila[col]))
                contar(n)
                en_fila[tipo] = eid
        for col, tipo in CLAVE_NOMBRE.items():
            if fila.get(col) not in (None, ""):
                eid, n = mundo.upsert_entity(tipo, fuente, nombre=str(fila[col]))
                contar(n)
                en_fila[tipo] = eid
        for desde, rel, hacia in RELACIONES:
            if desde in en_fila and hacia in en_fila:
                contar(mundo.relate(en_fila[desde], rel, en_fila[hacia], fuente, contexto)[1])
        for eid in en_fila.values():
            contar(mundo.assert_fact(eid, "visto_en", fuente["ref"], fuente, contexto)[1])
            entidades_vistas.add(eid)
        principal = next((en_fila[t] for t in PRIORIDAD if t in en_fila), None)
        fila = {k: v for k, v in fila.items() if v is not None}
        if principal:
            tipo_de = {**CLAVE_EXTERNA, **CLAVE_NOMBRE}
            claves = set(tipo_de)
            # Los hechos llevan como calificadores las otras cosas de la fila ("14 disputas" de RapidEnvio, en Norte).
            calif = {c: fila[c] for c in claves
                     if fila.get(c) not in (None, "") and en_fila.get(tipo_de[c]) != principal}
            for col, valor in fila.items():
                if col not in claves:
                    contar(mundo.assert_fact(principal, col, valor, fuente, contexto, calificadores=calif)[1])
    mundo.guardar()
    return {"nuevos": nuevos, "repetidos": repetidos, "entidades": len(entidades_vistas)}


def _checksum(filas) -> str:
    return "sha256:" + _hash(filas)[:16]


class MundoAgente:
    """El adaptador del World Model para el agente: tiempo límite, respaldo y su traza."""

    def __init__(self, cfg, traza, run_id: str):
        self.cfg, self.traza, self.run_id = cfg, traza, run_id
        self.motor: WorldModel | None = None
        self.contexto = id_contexto("corrida", run_id)
        self.verificadas = 0

    def _con_limite(self, accion, fn, avisar_apagado=True):
        if not self.cfg.mundo_activo:
            if avisar_apagado:
                self.traza.evento("mundo", "world-model", accion, estado="omitido",
                                  salida="World Model apagado (AGENTE_MUNDO=false): sin anclaje ni resolución de ids")
            return None
        with Cronometro() as t:
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                return pool.submit(fn).result(timeout=self.cfg.mundo_timeout_s)
            except TiempoAgotado:
                self.traza.evento("mundo", "world-model", accion, estado="error", ms=t.ms,
                                  salida=f"respaldo: el World Model tardó más de {self.cfg.mundo_timeout_s} s; "
                                         "sigue sin él")
            except Exception as e:  # noqa: BLE001 — cualquier falla cae al respaldo
                self.traza.evento("mundo", "world-model", accion, estado="error", ms=t.ms,
                                  salida=f"respaldo: el World Model falló ({type(e).__name__}: {e}); sigue sin él")
            finally:
                pool.shutdown(wait=False)
        return None

    def _abrir(self) -> WorldModel:
        if self.motor is None:
            carpeta = Path(self.cfg.mundo)
            semilla = Path(self.cfg.mundo_semilla) if self.cfg.mundo_semilla else None
            if semilla and (semilla / "eventos.jsonl").exists() and not (carpeta / "eventos.jsonl").exists():
                carpeta.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(semilla / "eventos.jsonl", carpeta / "eventos.jsonl")
            self.motor = WorldModel(carpeta)
        return self.motor

    def _fuente(self, ref, filas=None, kind="agent"):
        f = {"kind": kind, "by": "io-agent", "at": _ahora(), "runId": self.run_id, "ref": ref}
        if filas is not None:
            f["checksum"] = _checksum(filas)
        return f

    # -- escribir -------------------------------------------------------------------------
    def abrir_corrida(self, pregunta: str):
        """El contexto de la corrida y las disputas que nombra la pregunta (fuente: la persona)."""
        def hacer():
            with Cronometro() as t:
                motor = self._abrir()
                fuente = self._fuente("pregunta", kind="manual")
                _, nuevo = motor.upsert_context("corrida", self.run_id, fuente, attrs={"pregunta": pregunta})
                ids = [motor.upsert_entity("disputa", fuente, clave_externa=d)[0] for d in ID_DISPUTA.findall(pregunta)]
                motor.guardar()
            return ids, len(motor.entidades), len(motor.hechos), t.ms
        r = self._con_limite("abrir_corrida", hacer)
        if r:
            ids, n_ent, n_hechos, ms = r
            self.traza.evento("mundo", "world-model", "abrir_corrida", entrada=self.contexto,
                              salida=f"{len(ids)} disputa(s) de la pregunta · el mundo conoce {n_ent} entidades y "
                                     f"{n_hechos} hechos", ms=ms)

    def ingerir(self, evidencia: dict):
        if not evidencia.get("ok") or not evidencia.get("filas"):
            return

        def hacer():
            with Cronometro() as t:
                motor, fuente = self._abrir(), self._fuente(evidencia["id"], evidencia["filas"])
                r = ingerir_filas(motor, evidencia["filas"], self.contexto, fuente)
                # Una consulta filtrada por un id ("WHERE disputa_id = 'du_…'") que devolvió filas habla de esa
                # disputa aunque no la pida en el SELECT: también cuenta como vista.
                for d in dict.fromkeys(ID_DISPUTA.findall(evidencia.get("sql", ""))):
                    eid, n1 = motor.upsert_entity("disputa", fuente, clave_externa=d)
                    _, n2 = motor.assert_fact(eid, "visto_en", evidencia["id"], fuente, self.contexto)
                    r["nuevos"] += n1 + n2
                    r["entidades"] += 1
                motor.guardar()
            return r, t.ms
        r = self._con_limite("ingerir", hacer, avisar_apagado=False)
        if r:
            res, ms = r
            self.traza.evento("mundo", "world-model", "ingerir", entrada=f"{evidencia['id']} · {evidencia['n_filas']} filas",
                              salida=(f"{res['entidades']} entidades · {res['nuevos']} eventos nuevos · "
                                      f"{res['repetidos']} ya estaban (idempotente)") if res["entidades"] else
                                     "filas de conteo, sin cosas identificables: nada que ingerir", ms=ms)

    # -- leer -----------------------------------------------------------------------------
    def sugerir_id(self, sql: str) -> str:
        """Etapa resolve: un id de disputa del SQL que no existe tal cual, pero sí con otras mayúsculas."""
        def hacer():
            motor = self._abrir()
            conocidos = {e["attrs"]["clave_externa"] for e in motor.de_tipo("disputa")}
            pistas = []
            for d in dict.fromkeys(ID_DISPUTA.findall(sql)):
                if d in conocidos:
                    continue
                parecido = next((c for c in conocidos if c.lower() == d.lower()), None)
                if parecido:
                    pistas.append((d, parecido))
            return pistas
        pistas = self._con_limite("resolver", hacer, avisar_apagado=False) or []
        if not pistas:
            return ""
        texto = " ".join(f"{d} no existe; el id canónico es {c} (respeta mayúsculas)." for d, c in pistas)
        self.traza.evento("mundo", "investigador", "resolver", entrada=sql, salida=texto, estado="alerta")
        return f"\nWORLD MODEL: {texto}"

    def anclar(self, texto: str) -> list[str]:
        """Lo que la conclusión nombra (disputas, transportistas, regiones) y ninguna consulta de ESTA corrida
        devolvió. Devuelve los problemas para el Evaluador; vacío si todo está anclado o si está apagado."""
        def hacer():
            motor = self._abrir()
            vistos = motor.vistos_en(self.contexto)
            ancladas, problemas = [], []
            for d in dict.fromkeys(ID_DISPUTA.findall(texto)):
                eid = id_entidad("disputa", d)
                if eid in vistos:
                    ancladas.append((d, motor.donde_se_vio(eid, self.contexto)))
                else:
                    parecido = next((e["attrs"]["clave_externa"] for e in motor.de_tipo("disputa")
                                     if e["attrs"]["clave_externa"].lower() == d.lower()
                                     and e["attrs"]["clave_externa"] != d), None)
                    problemas.append(f"Nombras la disputa {d}, pero " + (
                        f"su id es {parecido}." if parecido else "ninguna consulta de esta corrida la devolvió."))
            plano = _sin_acentos(texto)
            for tipo in ("transportista", "region"):
                for e in motor.de_tipo(tipo):
                    nombre = e["attrs"].get("nombre", "")
                    if not nombre or not re.search(rf"\b{re.escape(_sin_acentos(nombre))}\b", plano):
                        continue  # se busca con su mayúscula: "Norte" es la región, "norte" no
                    if e["id"] in vistos:
                        ancladas.append((nombre, motor.donde_se_vio(e["id"], self.contexto)))
                    else:
                        problemas.append(f"Nombras {'la región' if tipo == 'region' else 'el transportista'} "
                                         f"{nombre}, pero ninguna consulta de esta corrida lo devolvió: consúltalo o "
                                         "no lo nombres (lo que recuerdas de otras corridas no es evidencia).")
            return ancladas, problemas
        r = self._con_limite("anclar", hacer)
        if r is None:
            return []
        ancladas, problemas = r
        self.verificadas = len(ancladas)
        self.traza.evento("mundo", "evaluador", "anclar", entrada=texto[:300],
                          salida=("; ".join(f"{n} ({', '.join(refs) or '-'})" for n, refs in ancladas) or "nada que anclar")
                                 + (" · sin anclar: " + " ".join(problemas) if problemas else ""),
                          estado="alerta" if problemas else "ok")
        return problemas


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
