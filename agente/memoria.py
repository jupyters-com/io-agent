"""H-MEM, el motor de memoria de Meterless (engines/hmem), implementado para IO (Paso 13).

Para qué lo usa IO: que el agente no empiece de cero en cada corrida. Recuerda dos cosas:

  - Lecciones del Evaluador (tipo "preference", dominio "metodo"): cada vez que el Evaluador devuelve
    un veredicto o una conclusión, el motivo queda como lección. En la próxima corrida se le recuerda al
    Investigador ANTES de empezar, para que no repita el error (y no gaste vueltas en devoluciones).
  - Hallazgos (tipo "factual", dominio "disputas"): lo que concluyó cada corrida y cómo quedó cada
    hipótesis. Entran como pistas, nunca como evidencia: el Evaluador sigue exigiendo una consulta de
    ESTA corrida para cada afirmación.

Qué tomamos del plano de H-MEM (HOW_TO_USE_H-MEM.md y reference/src):
  - El registro de memoria (id, content, type, layer, confidence, source obligatorio, tags, domain,
    entities, related_to, supersedes/superseded_by, derived_from, provenance).
  - Capas short_term / working / long_term, con promoción a long_term cuando una memoria ayuda varias veces.
  - El ranking híbrido de 8 señales, recortado a [0, 1] y multiplicado por la confianza, con top-N y umbral.
  - La reinyección agrupada por dominio con marcas de capa, entidades e id.
  - La retroalimentación con los deltas exactos (helpful +0.05, not_helpful -0.03, wrong -0.20).
  - El libro de confianza (trust ledger) de solo agregar: cada cambio deja su estado anterior y nuevo.
  - Lo reemplazado se penaliza (superseded), nunca se borra.
Lo que no implementamos (no hace falta para IO en el hackathon): dreaming, sleep cycle y el detector
de conflictos con modelo. El "embedding" es el determinista del plano de referencia (hash por palabra).

Todo pasa por Memoria (el adaptador): con tiempo límite y respaldo. Si H-MEM está apagado
(AGENTE_HMEM=false), tarda más de AGENTE_HMEM_TIMEOUT_S o falla, el agente sigue SIN memoria y la
traza lo dice. Los datos viven en <AGENTE_MEMORIA>/memorias.json y <AGENTE_MEMORIA>/ledger.jsonl.
"""

import hashlib
import json
import math
import re
import shutil
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TiempoAgotado
from pathlib import Path

from agente.traza import Cronometro

DIA_MS = 24 * 60 * 60 * 1000
DIM = 64
TOP_N = 5
UMBRAL = 0.30            # sobre el puntaje final (después de multiplicar por la confianza); el plano usa 0.35,
                         # afinado para IO: las conclusiones largas diluyen la coincidencia de palabras
# Ajuste por dominio (el plano pide afinar por dominio): las lecciones de método no comparten palabras con
# la pregunta, así que se buscan con una consulta fija y un umbral más bajo.
UMBRAL_LECCIONES = 0.20
TOPE_ENTIDADES = 10
TOPE_RELACIONES = 5
RECENCIA_DIAS = 14
DELTAS = {"helpful": 0.05, "not_helpful": -0.03, "wrong": -0.20}
PESO_CAPA = {"long_term": 1.0, "working": 0.8, "short_term": 0.6}
PROMOVER_CON_ACCESOS = 3  # una memoria que ayudó en 3 corridas pasa a long_term

# Consulta fija para recordar las lecciones de método (no dependen de la pregunta).
CONSULTA_LECCIONES = ("leccion evaluador metodo concluir hipotesis contraria veredicto evidencia "
                      "recomendacion decisiones razon")
VOCABULARIO = {"fraude", "transportista", "region", "reembolso", "contracargo", "disputa", "disputas",
               "pelear", "resolver", "reembolsar", "aceptar", "reclamo", "entrega", "atraso", "extraviado"}
PALABRAS_VACIAS = {"de", "la", "el", "en", "y", "a", "los", "las", "del", "que", "por", "con", "un", "una",
                   "es", "se", "no", "su", "al", "lo", "para", "pena", "vale", "como", "mas", "sin"}


# -- texto -----------------------------------------------------------------------------------
def _sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def tokenizar(texto: str) -> list[str]:
    limpio = re.sub(r"[^a-z0-9_\s]", " ", _sin_acentos(texto).lower())
    return [t for t in limpio.split() if len(t) > 1 and t not in PALABRAS_VACIAS]


def _fnv1a(s: str) -> int:
    h = 0x811C9DC5
    for c in s.encode("utf-8"):
        h ^= c
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def incrustar(texto: str) -> list[float]:
    """El embedder determinista del plano de referencia: hash FNV-1a por palabra en 64 dimensiones."""
    v = [0.0] * DIM
    for t in tokenizar(texto):
        h = _fnv1a(t)
        v[h % DIM] += (1 if (h >> 8) % 2 == 0 else -1) * (1 + ((h >> 16) % 8) / 8)
    norma = math.sqrt(sum(x * x for x in v))
    return v if norma == 0 else [x / norma for x in v]


def coseno(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def jaccard(a, b) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / (len(sa) + len(sb) - inter)


def entidades(texto: str) -> list[str]:
    """Ids de disputa (du_…), nombres propios (RapidEnvio, Norte) y términos del dominio."""
    vistas = []
    for m in re.findall(r"\bdu_[A-Za-z0-9]+\b", texto):
        vistas.append(m.lower())
    for m in re.finditer(r"\b([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]{2,})\b", texto):
        antes = texto[:m.start()].rstrip()
        if not antes or antes[-1] in ".!?¿¡«(\"":  # mayúscula por empezar frase, no por ser nombre propio
            continue
        vistas.append(_sin_acentos(m.group(1)).lower())
    vistas += [t for t in tokenizar(texto) if t in VOCABULARIO]
    descartar = {"para", "las", "los", "del", "una", "hay", "pregunta", "por", "que", "hipotesis", "recomendacion",
                 "conclusion", "concluyo", "sostenida", "descartada", "lo", "io", "leccion", "evaluador", "explicar",
                 "consulta", "usa", "hace", "falta", "segun", "solo", "aunque", "este", "esta", "ese", "esa"}
    salida = []
    for e in vistas:
        if e not in salida and e not in descartar and e not in PALABRAS_VACIAS:
            salida.append(e)
    return salida[:TOPE_ENTIDADES]


def dominio_de(pregunta: str) -> str:
    """Una pregunta sobre una disputa concreta vive en su propio dominio (disputa/du_…); las demás, en
    "disputas". Así lo aprendido de una disputa no se confunde con otra parecida."""
    m = re.search(r"\bdu_[A-Za-z0-9]+\b", pregunta)
    return f"disputa/{m.group(0).lower()}" if m else "disputas"


def _ahora_ms() -> int:
    return int(time.time() * 1000)


def _foto(m: dict) -> dict:
    return {k: v for k, v in m.items() if k != "embedding"}


# -- el motor --------------------------------------------------------------------------------
class LibroDeConfianza:
    """Trust ledger: solo se agrega. Cada mutación deja quién, qué y el estado anterior y nuevo."""

    def __init__(self, carpeta: Path, reloj):
        self.ruta, self.reloj = carpeta / "ledger.jsonl", reloj

    def anotar(self, memoria_id, accion, actor, anterior=None, nuevo=None, detalles=None):
        entrada = {"memoryId": memoria_id, "action": accion, "actor": actor, "timestamp": self.reloj()}
        if anterior is not None:
            entrada["previousState"] = anterior
        if nuevo is not None:
            entrada["newState"] = nuevo
        if detalles:
            entrada["details"] = detalles
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")

    def entradas(self) -> list[dict]:
        if not self.ruta.exists():
            return []
        return [json.loads(l) for l in self.ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


class HMEM:
    """Almacén por capas + minado + ranking + reinyección + retroalimentación, con su libro de confianza."""

    def __init__(self, carpeta: Path, actor: str = "io-agent", reloj=_ahora_ms):
        self.carpeta, self.actor, self.reloj = Path(carpeta), actor, reloj
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.ruta = self.carpeta / "memorias.json"
        self.libro = LibroDeConfianza(self.carpeta, reloj)
        self.secuencia, self.memorias = 0, {}
        if self.ruta.exists():
            guardado = json.loads(self.ruta.read_text(encoding="utf-8"))
            self.secuencia = guardado["seq"]
            for m in guardado["records"]:
                m["embedding"] = incrustar(m["content"])  # se recalcula: no se guarda
                self.memorias[m["id"]] = m

    def guardar(self):
        registros = [_foto(m) for m in sorted(self.memorias.values(), key=lambda m: int(m["id"].split("-")[1]))]
        self.ruta.write_text(json.dumps({"seq": self.secuencia, "records": registros}, ensure_ascii=False, indent=2)
                             + "\n", encoding="utf-8")

    # -- escribir --------------------------------------------------------------------------
    def agregar(self, contenido, tipo, capa, fuente, dominio, etiquetas=(), confianza=0.7, origen="goal_run",
                refs=None, derivada_de=()):
        if not str(fuente or "").strip():
            raise ValueError("H-MEM: una memoria sin fuente se rechaza por construcción")
        ahora = self.reloj()
        self.secuencia += 1
        m = {
            "id": f"mem-{self.secuencia}", "content": contenido, "type": tipo, "layer": capa,
            "timestamp": ahora, "lastAccessed": ahora, "accessCount": 0,
            "tags": list(etiquetas), "domain": dominio, "namespace": f"{dominio}/"
            + ("profile" if tipo == "preference" else "facts" if tipo == "factual" else "notes"),
            "confidence": round(max(0.0, min(1.0, confianza)), 4), "source": fuente,
            "provenance": {"origin": origen, "learnedAt": ahora, "label": fuente, "refs": refs or {}},
            "entities": entidades(contenido), "relatedTo": [], "supersedes": None, "supersededBy": None,
            "derivedFrom": list(derivada_de), "embedding": incrustar(contenido),
        }
        for otra in self.memorias.values():  # relaciones: misma entidad y mismo dominio (tope 5, en los dos sentidos)
            if len(m["relatedTo"]) >= TOPE_RELACIONES:
                break
            if otra["domain"] == dominio and set(otra["entities"]) & set(m["entities"]):
                m["relatedTo"].append(otra["id"])
                if len(otra["relatedTo"]) < TOPE_RELACIONES:
                    otra["relatedTo"].append(m["id"])
        self.memorias[m["id"]] = m
        self.libro.anotar(m["id"], "create", self.actor, nuevo=_foto(m))
        return m

    def reemplazar(self, vieja_id, nueva_id, motivo):
        """La nueva memoria reemplaza a la vieja: la vieja queda penalizada en el ranking, no se borra."""
        vieja, nueva = self.memorias[vieja_id], self.memorias[nueva_id]
        antes = _foto(vieja)
        vieja["supersededBy"], nueva["supersedes"] = nueva_id, vieja_id
        self.libro.anotar(vieja_id, "supersede", self.actor, anterior=antes, nuevo=_foto(vieja),
                          detalles={"por": nueva_id, "motivo": motivo})

    def retroalimentar(self, memoria_id, senal, motivo=""):
        m = self.memorias[memoria_id]
        antes = _foto(m)
        if senal == "helpful":
            m["accessCount"] += 1
        m["confidence"] = round(max(0.0, min(1.0, m["confidence"] + DELTAS[senal])), 4)
        if senal == "wrong" and "review" not in m["tags"]:
            m["tags"].append("review")
        self.libro.anotar(memoria_id, "feedback", self.actor, anterior=antes, nuevo=_foto(m),
                          detalles={"kind": senal, "delta": DELTAS[senal], "motivo": motivo})
        if senal == "helpful" and m["layer"] != "long_term" and m["accessCount"] >= PROMOVER_CON_ACCESOS:
            antes = _foto(m)
            m["layer"] = "long_term"
            self.libro.anotar(memoria_id, "promote", self.actor, anterior=antes, nuevo=_foto(m))

    # -- leer ------------------------------------------------------------------------------
    def puntaje(self, m, consulta, dominio, etiquetas=()) -> float:
        fichas = tokenizar(consulta)[:8]
        edad_dias = (self.reloj() - m["lastAccessed"]) / DIA_MS
        crudo = (0.35 * max(0.0, min(1.0, coseno(incrustar(consulta), m["embedding"])))
                 + 0.20 * jaccard(fichas, tokenizar(m["content"]))
                 + 0.10 * jaccard(list(etiquetas) or fichas, [t.lower() for t in m["tags"]])
                 + 0.10 * (1 if m["domain"] == dominio else 0)
                 + 0.15 * jaccard(entidades(consulta), m["entities"])
                 + 0.05 * PESO_CAPA[m["layer"]]
                 + 0.05 * math.exp(-edad_dias / RECENCIA_DIAS)
                 - 0.20 * (1 if m["supersededBy"] else 0))
        return max(0.0, min(1.0, crudo)) * m["confidence"]

    def recordar(self, consulta, dominio, tipo=None, top_n=TOP_N, umbral=UMBRAL, etiquetas=()) -> list[tuple[dict, float]]:
        candidatas = [(m, self.puntaje(m, consulta, dominio, etiquetas)) for m in self.memorias.values()
                      if tipo is None or m["type"] == tipo]
        elegidas = sorted([c for c in candidatas if c[1] >= umbral],
                          key=lambda c: (-c[1], int(c[0]["id"].split("-")[1])))[:top_n]
        for m, s in elegidas:
            m["lastAccessed"] = self.reloj()
            self.libro.anotar(m["id"], "read", self.actor, detalles={"query": consulta[:200], "score": round(s, 4)})
        return elegidas


def reinyectar(elegidas: list[tuple[dict, float]]) -> str:
    """Bloques agrupados por dominio, con marca de capa, entidades e id (formato de reinyección de H-MEM)."""
    if not elegidas:
        return ""
    lineas = ["MEMORIA DE IO (H-MEM): lo aprendido en corridas anteriores.",
              "- Las lecciones del método son reglas que el Evaluador ya te hizo cumplir: síguelas desde el principio.",
              "- Los hallazgos son pistas, NO evidencia. Aunque creas saber la respuesta, haz el método completo en",
              "  ESTA corrida: 2 o más hipótesis (incluida la contraria), una consulta por hipótesis, veredictos,",
              "  contar las decisiones con razon_decision y recién entonces concluir."]
    por_dominio: dict[str, list[dict]] = {}
    for m, _ in elegidas:
        por_dominio.setdefault(m["domain"], []).append(m)
    # El método primero: es lo que más ahorra vueltas.
    for dominio in sorted(por_dominio, key=lambda d: (d != "metodo", d)):
        lineas.append(f"## {dominio}")
        for m in por_dominio[dominio]:
            marca = {"long_term": "LT", "working": "WK", "short_term": "ST"}[m["layer"]]
            ents = f" (entidades: {', '.join(m['entities'][:5])})" if m["entities"] else ""
            lineas.append(f"- [{marca}] {m['content']}{ents} <{m['id']}>")
    return "\n".join(lineas)


# -- minado desde una corrida -------------------------------------------------------------------
def _regla(problema: str) -> str:
    """El motivo del Evaluador como regla general: sin lo propio de la corrida (H2 -> H#, E5 -> E#, el id de
    la disputa, las cantidades y lo citado entre comillas). Se conservan los números de las reglas
    ("al menos 2 hipótesis", "2 o más señales")."""
    texto = re.sub(r"\bH\d+\b", "H#", problema)
    texto = re.sub(r"\bE\d+\b", "E#", texto)
    texto = re.sub(r"\bdu_[A-Za-z0-9]+\b", "du_…", texto)
    texto = re.sub(r'"[^"]*"', '"…"', texto)
    texto = re.sub(r"\b\d+(?:[.,]\d+)?\b(?!\s+(?:hipótesis|o más))", "N", texto)
    texto = re.sub(r"H#(?:\s*,\s*H#)+", "H#", texto)  # "sin veredicto: H2, H3, H4" es la misma lección
    return " ".join(texto.split())


def _clave(regla: str) -> str:
    """Identifica la misma lección aunque cambien las cantidades, lo citado entre comillas o los ejemplos entre
    paréntesis ("sin términos técnicos (product_not_received)" y "(causa_operativa)" son la misma)."""
    texto = re.sub(r"\d+(?:[.,]\d+)?", "N", regla)
    texto = re.sub(r'"[^"]*"', '"…"', texto)
    texto = re.sub(r"\([^)]*\)", "(…)", texto)
    return hashlib.sha1(_sin_acentos(texto).lower().encode()).hexdigest()[:10]


class Memoria:
    """El adaptador de H-MEM para el agente: tiempo límite, respaldo (seguir sin memoria) y su traza."""

    def __init__(self, cfg, traza, nombre_pregunta: str):
        self.cfg, self.traza, self.etiqueta_pregunta = cfg, traza, f"pregunta:{nombre_pregunta}"
        self.motor: HMEM | None = None
        self.usadas: list[str] = []
        self.contexto = ""
        self._pendientes: list[tuple] | None = []  # eventos guardados hasta que la corrida se anuncie

    def _anotar(self, *args, **kw):
        if self._pendientes is None:
            self.traza.evento(*args, **kw)
        else:
            self._pendientes.append((args, kw))

    def publicar(self):
        """Escribe en la traza los eventos de memoria que ocurrieron antes de recibir_pregunta."""
        pendientes, self._pendientes = self._pendientes or [], None
        for args, kw in pendientes:
            self.traza.evento(*args, **kw)

    # Toda llamada al motor pasa por aquí: si se pasa del tiempo o falla, se sigue sin memoria.
    def _con_limite(self, accion, fn):
        if not self.cfg.hmem:
            self._anotar("memoria", "h-mem", accion, estado="omitido",
                              salida="H-MEM apagado (AGENTE_HMEM=false o SEMANTIC_LAYER=off): el agente corre sin memoria")
            return None
        with Cronometro() as t:
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                return pool.submit(fn).result(timeout=self.cfg.hmem_timeout_s)
            except TiempoAgotado:
                self._anotar("memoria", "h-mem", accion, estado="error", ms=t.ms,
                                  salida=f"respaldo: H-MEM tardó más de {self.cfg.hmem_timeout_s} s; sigue sin memoria")
            except Exception as e:  # noqa: BLE001 — cualquier falla de la memoria cae al respaldo
                self._anotar("memoria", "h-mem", accion, estado="error", ms=t.ms,
                                  salida=f"respaldo: H-MEM falló ({type(e).__name__}: {e}); sigue sin memoria")
            finally:
                pool.shutdown(wait=False)
        return None

    def _abrir(self) -> HMEM:
        if self.motor is None:
            carpeta = Path(self.cfg.memoria)
            semilla = Path(self.cfg.memoria_semilla) if self.cfg.memoria_semilla else None
            if semilla and (semilla / "memorias.json").exists() and not (carpeta / "memorias.json").exists():
                carpeta.mkdir(parents=True, exist_ok=True)
                for nombre in ("memorias.json", "ledger.jsonl"):
                    if (semilla / nombre).exists():
                        shutil.copyfile(semilla / nombre, carpeta / nombre)
            self.motor = HMEM(carpeta)
        return self.motor

    def recordar(self, pregunta: str) -> str:
        """Antes de la primera vuelta: busca lecciones y hallazgos y arma el bloque que se reinyecta."""
        def hacer():
            with Cronometro() as t:
                motor = self._abrir()
                lecciones = motor.recordar(CONSULTA_LECCIONES, "metodo", tipo="preference", umbral=UMBRAL_LECCIONES,
                                           etiquetas=["leccion"])
                hallazgos = motor.recordar(pregunta, dominio_de(pregunta), tipo="factual", umbral=self.cfg.hmem_umbral,
                                           etiquetas=[self.etiqueta_pregunta, "hallazgo"])
                motor.guardar()
            return lecciones, hallazgos, len(motor.memorias), t.ms
        r = self._con_limite("recordar", hacer)
        if r is None:
            return ""
        lecciones, hallazgos, total, ms = r
        elegidas = lecciones + hallazgos
        self.usadas = [m["id"] for m, _ in elegidas]
        self.contexto = reinyectar(elegidas)
        detalle = ", ".join(f"{m['id']} {m['type']} {s:.2f}" for m, s in elegidas) or "ninguna supera el umbral"
        self._anotar("memoria", "investigador", "recordar", entrada=pregunta,
                          salida=f"{len(lecciones)} lecciones + {len(hallazgos)} hallazgos de {total} memorias · {detalle}",
                          ms=ms)
        return self.contexto

    def aprender(self, pregunta: str, run_id: str, resultado: dict, devoluciones: list[str]):
        """Al final: guarda las lecciones nuevas del Evaluador y, si concluyó, los hallazgos de la corrida.
        Retroalimenta las memorias que se usaron (helpful si ayudaron, not_helpful si no)."""
        def hacer():
            motor = self._abrir()
            fuente = f"corrida:{run_id}"
            nuevas, reforzadas, reemplazadas = [], [], []
            # 1. Lecciones: una por motivo distinto del Evaluador
            reglas_de_hoy = set()
            for problema in devoluciones:
                regla = _regla(problema)
                clave = f"regla:{_clave(regla)}"
                reglas_de_hoy.add(clave)
                existente = next((m for m in motor.memorias.values() if clave in m["tags"]), None)
                if existente:
                    if existente["id"] not in reforzadas and existente["id"] not in self.usadas:
                        motor.retroalimentar(existente["id"], "helpful", "el Evaluador volvió a devolver por lo mismo")
                        reforzadas.append(existente["id"])
                    continue
                m = motor.agregar(f"Lección del Evaluador: {regla}", "preference", "working", fuente, "metodo",
                                  etiquetas=["leccion", clave], confianza=0.8, origen="decision",
                                  refs={"goalRunId": run_id})
                nuevas.append(m["id"])
            # 2. Retroalimentación de lo que se recordó en esta corrida
            for mid in self.usadas:
                m = motor.memorias.get(mid)
                if not m:
                    continue
                if m["type"] == "preference":
                    repetida = next((t for t in m["tags"] if t.startswith("regla:")), None) in reglas_de_hoy
                    motor.retroalimentar(mid, "not_helpful" if repetida else "helpful",
                                         "la lección no evitó la devolución" if repetida else
                                         "no hubo devolución por esta lección")
                else:
                    ok = resultado["estado"] == "concluida"
                    motor.retroalimentar(mid, "helpful" if ok else "not_helpful",
                                         "la corrida concluyó" if ok else "la corrida se abstuvo")
            # 3. Hallazgos: solo de corridas concluidas; reemplazan a los de la misma pregunta
            if resultado["estado"] == "concluida":
                previas = [m for m in motor.memorias.values()
                           if self.etiqueta_pregunta in m["tags"] and not m["supersededBy"]]
                base = ["hallazgo", self.etiqueta_pregunta]
                conclusion = motor.agregar(
                    f"Para «{pregunta}» IO concluyó: {resultado['conclusion']}"
                    + (f" Recomendación: {resultado['recomendacion']}" if resultado.get("recomendacion") else ""),
                    "factual", "working", fuente, dominio_de(pregunta), etiquetas=base + ["conclusion"], confianza=0.7,
                    refs={"goalRunId": run_id})
                nuevas.append(conclusion["id"])
                for h in resultado["hipotesis"]:
                    if h["veredicto"] not in ("sostenida", "descartada"):
                        continue
                    m = motor.agregar(f"Para «{pregunta}», hipótesis «{h['enunciado']}»: {h['veredicto']}. "
                                      f"{h.get('razon', '')}", "factual", "working", fuente, dominio_de(pregunta),
                                      etiquetas=base + [f"veredicto:{h['veredicto']}"], confianza=0.7,
                                      refs={"goalRunId": run_id}, derivada_de=[conclusion["id"]])
                    nuevas.append(m["id"])
                for vieja in previas:
                    motor.reemplazar(vieja["id"], conclusion["id"], "hay una corrida más reciente de la misma pregunta")
                    reemplazadas.append(vieja["id"])
            motor.guardar()
            return nuevas, reforzadas, reemplazadas, len(motor.memorias)
        with Cronometro() as t:
            r = self._con_limite("aprender", hacer)
        if r is None:
            return
        nuevas, reforzadas, reemplazadas, total = r
        self._anotar("memoria", "h-mem", "aprender", entrada=f"corrida {run_id} · {resultado['estado']}",
                          salida=f"{len(nuevas)} nuevas ({', '.join(nuevas) or '-'}) · {len(reforzadas)} reforzadas · "
                                 f"{len(reemplazadas)} reemplazadas · {len(self.usadas)} retroalimentadas · "
                                 f"{total} en total", ms=t.ms)
