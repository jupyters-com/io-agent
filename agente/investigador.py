"""El Investigador (Paso 10): propone hipótesis, las prueba con consultar(sql) y descarta las que
la evidencia no sostiene, dejando anotada cada prueba.

Cómo funciona: un ciclo de conversación con el modelo (Nemotron, vía Nightshift). En cada vuelta
el modelo responde UNA acción en JSON; nuestro código la ejecuta, la registra y le devuelve el
resultado. La IA piensa; el código hace y anota:

  hipotesis  -> se registran H1, H2, …
  consultar  -> se corre consultar(sql); el resultado queda como evidencia E1, E2, …
  veredicto  -> sostenida / descartada, citando E#. El Evaluador lo revisa antes de aceptarlo.
  concluir   -> el Evaluador revisa todo; si falta evidencia, se lo devuelve al modelo.
  abstenerse -> no hay evidencia suficiente: IO prefiere no concluir a inventar.

Topes: AGENTE_MAX_ITERACIONES vueltas (cada llamada al modelo cuenta una) y AGENTE_TIMEOUT_S por
llamada. Si se acaba el tope sin conclusión aceptada, se abstiene.
"""

import json
import re

from agente import evaluador
from agente.esquema import ESQUEMA
from agente.modelo import SinMasRespuestas
from agente.traza import Cronometro

MAX_FILAS_AL_MODELO = 30

SISTEMA = f"""Eres el Investigador de IO, un agente que explica por qué pasan las cosas en los datos de una
tienda online. Investigas disputas de pago (contracargos). Respondes en español.

Solo ves datos con la herramienta consultar(sql), sobre este esquema:
{ESQUEMA}

Responde SIEMPRE con UN solo objeto JSON y nada más (sin texto alrededor). Acciones posibles:

1. Proponer hipótesis:
   {{"accion": "hipotesis", "hipotesis": [{{"id": "H1", "enunciado": "..."}}, {{"id": "H2", "enunciado": "..."}}]}}
2. Probar una hipótesis con una consulta (una por vez):
   {{"accion": "consultar", "hipotesis": "H1", "sql": "SELECT ..."}}
   Te devolveré el resultado con un id de evidencia (E1, E2, …).
3. Dar un veredicto, citando la evidencia que lo prueba:
   {{"accion": "veredicto", "hipotesis": "H1", "veredicto": "descartada", "razon": "...", "evidencia": ["E1"]}}
   veredicto: "sostenida" o "descartada". La razón debe usar los números de las filas.
4. Concluir (solo cuando todas las hipótesis tengan veredicto y al menos una esté sostenida):
   {{"accion": "concluir", "conclusion": "...", "recomendacion": "..."}}
5. Abstenerse, si los datos no alcanzan para concluir con evidencia:
   {{"accion": "abstenerse", "razon": "..."}}

Para avanzar más rápido puedes mandar VARIAS acciones en una sola respuesta, en una lista:
   {{"acciones": [{{"accion": "consultar", "hipotesis": "H1", "sql": "..."}}, {{"accion": "consultar", "hipotesis": "H2", "sql": "..."}}]}}
Se ejecutan en orden y te devuelvo todos los resultados juntos. Lo ideal: una respuesta con todas las
hipótesis, otra con todas sus consultas, otra con todos los veredictos y la conclusión al final de la lista.

Método:
- Empieza proponiendo de 2 a 4 hipótesis. Incluye siempre la explicación más obvia a primera vista
  (por ejemplo, "es fraude"), aunque sospeches que es falsa: hay que probarla o descartarla con datos.
- Prueba cada hipótesis con al menos una consulta antes de darle veredicto.
- Nunca afirmes algo que no esté en las filas de una evidencia. Mejor abstenerse que inventar.
- Si la pregunta es por un aumento: compáralo con el período anterior y averigua DÓNDE se concentra
  (transportista y región, motivo, clientes). Una hipótesis sobre el grupo se mide sobre TODO el grupo del
  aumento con conteos: por ejemplo, la de fraude se prueba contando cuántas de esas disputas tienen
  sospecha_fraude ("2 de 18"), no con tasas por motivo.
- Antes de concluir sobre un grupo de disputas, cuenta cuántas caen en cada razon_decision, para que la
  recomendación diga cuántas pelear, cuántas resolver con el cliente, cuántas reembolsar, etc.
- La conclusión, la recomendación y las razones las lee la dueña de la tienda, que no conoce la base de
  datos: escríbelas en español simple, con conteos ("14 de las 18 disputas") en vez de tasas decimales, y
  SIN nombres de columnas ni expresiones como "zona_con_atrasos=true". La conclusión nombra la causa
  concreta (quién y dónde) en 1 a 3 frases.

Recomendaciones de IO (úsalas en "recomendacion"):
- vale_pelear: pelear la disputa con la prueba de entrega y el historial del cliente.
- no se pelea por reclamo_previo: resolver con el cliente (contactarlo, disculparse, ofrecer un descuento
  o un reembolso parcial y pedirle que retire la disputa).
- sin_entrega: no pelear y reembolsar.
- sospecha_de_fraude: no pelear; aceptar la disputa y marcar al cliente.
- causa_operativa en un transportista y región: reclamarle al transportista y revisar esa ruta.
"""


def _extraer_acciones(texto: str) -> list[dict]:
    """Las acciones del primer objeto JSON del texto (tolera ```json … ``` y texto alrededor).
    Acepta una acción sola ({"accion": …}) o varias ({"acciones": [ … ]})."""
    limpio = re.sub(r"```(?:json)?", "", texto).strip()
    inicio = limpio.find("{")
    if inicio < 0:
        raise ValueError("no encontré un objeto JSON")
    objeto, _ = json.JSONDecoder().raw_decode(limpio[inicio:])
    if isinstance(objeto, dict) and isinstance(objeto.get("acciones"), list):
        acciones = [a for a in objeto["acciones"] if isinstance(a, dict) and "accion" in a]
        if acciones:
            return acciones
    if isinstance(objeto, dict) and "accion" in objeto:
        return [objeto]
    raise ValueError('el JSON no tiene "accion" ni "acciones"')


def _normalizar_veredicto(valor) -> str:
    """Acepta variantes ("descartado", "rechazada", "confirmada") y las lleva a las dos válidas."""
    v = str(valor or "").strip().lower()
    if v.startswith(("descart", "rechaz", "refut", "falsa", "no sosten")):
        return "descartada"
    if v.startswith(("sosten", "confirm", "acept", "verdader", "valid")):
        return "sostenida"
    return v


def _refs_evidencia(valor) -> list[str]:
    """Los ids E# citados, aunque el modelo los escriba como "E1 (fila 2)", "e1" o "E1, E2"."""
    textos = valor if isinstance(valor, list) else [valor]
    refs = []
    for t in textos:
        for n in re.findall(r"\b[Ee](\d+)\b", str(t)):
            if f"E{n}" not in refs:
                refs.append(f"E{n}")
    return refs


def _filas_para_el_modelo(r: dict) -> str:
    filas = r.get("filas", [])[:MAX_FILAS_AL_MODELO]
    extra = f" (te muestro {len(filas)} de {r.get('n_filas')})" if r.get("n_filas", 0) > len(filas) else ""
    return json.dumps(filas, ensure_ascii=False, default=str) + extra


class Investigador:
    def __init__(self, cfg, fuente, llm, traza, consultar_fn, registrar_evidencia):
        self.cfg, self.fuente, self.llm, self.traza = cfg, fuente, llm, traza
        self.consultar_fn, self.registrar_evidencia = consultar_fn, registrar_evidencia
        self.hipotesis: dict[str, dict] = {}
        self.evidencia: dict[str, dict] = {}
        self.evidencia_por_hipotesis: dict[str, list[str]] = {}
        self.iteraciones = 0
        self.fallo_modelo = False  # True si la corrida terminó porque el modelo no respondió

    # -- acciones -----------------------------------------------------------------------------
    def _hipotesis(self, a):
        nuevas = []
        for h in a.get("hipotesis", []):
            hid = str(h.get("id") or f"H{len(self.hipotesis) + 1}").strip()
            if not re.fullmatch(r"H\d+", hid) or hid in self.hipotesis:
                hid = f"H{len(self.hipotesis) + 1}"
            self.hipotesis[hid] = {"id": hid, "enunciado": str(h.get("enunciado", "")).strip(),
                                   "veredicto": "sin_decidir", "razon": "", "evidencia": []}
            nuevas.append(f"{hid}: {self.hipotesis[hid]['enunciado']}")
        if not nuevas:
            return "ERROR: no propusiste ninguna hipótesis."
        self.traza.evento("investigador", "agente", "proponer_hipotesis", salida=" | ".join(nuevas))
        return f"Registradas: {', '.join(n.split(':')[0] for n in nuevas)}. Ahora pruébalas con consultas."

    def _consultar(self, a):
        sql, hid = str(a.get("sql", "")).strip(), str(a.get("hipotesis", "")).strip()
        if not sql:
            return 'ERROR: falta "sql".'
        r = self.consultar_fn(self.fuente, sql, self.traza, self.cfg, etiqueta=hid)
        eid = f"E{len(self.evidencia) + 1}"
        e = {"id": eid, "sql": " ".join(sql.split()), "motor": r.get("motor"), "ok": bool(r.get("ok")),
             "filas": r.get("filas", []), "n_filas": int(r.get("n_filas", 0)), "error": r.get("error")}
        self.evidencia[eid] = e
        if hid:
            self.evidencia_por_hipotesis.setdefault(hid, []).append(eid)
        self.registrar_evidencia(e, hid)
        if not e["ok"]:
            return f"RESULTADO {eid}: la consulta falló: {e['error']}. Corrígela o prueba otra."
        return f"RESULTADO {eid} (motor {e['motor']}, {e['n_filas']} filas): {_filas_para_el_modelo(r)}"

    def _veredicto(self, a):
        hid = str(a.get("hipotesis", "")).strip()
        if hid not in self.hipotesis:
            return f"ERROR: la hipótesis {hid!r} no existe. Existen: {', '.join(self.hipotesis) or 'ninguna'}."
        razon = str(a.get("razon", "")).strip()
        citada = next((a[k] for k in ("evidencia", "evidencias", "evidence", "refs") if a.get(k)), [])
        refs, origen = _refs_evidencia(citada), "citada"
        if not refs:  # la mencionó en la razón ("según E2, …")
            refs, origen = _refs_evidencia(razon), "en la razón"
        if not refs:  # la consulta que el propio modelo hizo para probar esta hipótesis
            refs = [e for e in self.evidencia_por_hipotesis.get(hid, []) if self.evidencia[e]["ok"]]
            origen = "consulta de la hipótesis"
        v = {"hipotesis": hid, "veredicto": _normalizar_veredicto(a.get("veredicto")),
             "razon": razon, "evidencia": refs}
        if v["veredicto"] not in ("sostenida", "descartada"):
            return f'ERROR: "veredicto" debe ser "sostenida" o "descartada" (recibí {a.get("veredicto")!r}).'
        problemas = evaluador.revisar_veredicto(v, self.evidencia)
        self.traza.evento("evaluador", "investigador", "revisar_veredicto",
                          entrada=f"{hid} {v['veredicto']} con {', '.join(v['evidencia']) or 'sin evidencia'}"
                                  + (f" ({origen})" if v["evidencia"] else ""),
                          salida="aceptado" if not problemas else "devuelto: " + " ".join(problemas),
                          estado="ok" if not problemas else "alerta")
        if problemas:
            return ("EVALUADOR: no acepto ese veredicto. " + " ".join(problemas) +
                    f' Formato: {{"accion": "veredicto", "hipotesis": "{hid}", "veredicto": "descartada", '
                    '"razon": "...", "evidencia": ["E1"]}')
        h = self.hipotesis[hid]
        h.update(veredicto=v["veredicto"], razon=v["razon"], evidencia=v["evidencia"])
        accion = "descartar" if v["veredicto"] == "descartada" else "sostener"
        self.traza.evento("investigador", "agente", accion, entrada=f"{hid}: {h['enunciado']}",
                          salida=f"evidencia {', '.join(v['evidencia'])} · {v['razon']}")
        return f"Veredicto de {hid} aceptado."

    def _ejecutar(self, a):
        """Ejecuta una acción. Devuelve (respuesta_final, None) si la corrida termina, o (None, texto)."""
        accion = a.get("accion")
        if accion == "hipotesis":
            return None, self._hipotesis(a)
        if accion == "consultar":
            return None, self._consultar(a)
        if accion == "veredicto":
            return None, self._veredicto(a)
        if accion == "concluir":
            problemas = evaluador.revisar_conclusion(self.hipotesis, self.evidencia,
                                                     str(a.get("conclusion", "")), str(a.get("recomendacion", "")))
            self.traza.evento("evaluador", "investigador", "revisar_conclusion",
                              entrada=str(a.get("conclusion", ""))[:300],
                              salida="aceptada" if not problemas else "devuelta: " + " ".join(problemas),
                              estado="ok" if not problemas else "alerta")
            if not problemas and str(a.get("conclusion", "")).strip():
                return self._final("concluida", conclusion=str(a["conclusion"]).strip(),
                                   recomendacion=str(a.get("recomendacion", "")).strip() or None), None
            return None, "EVALUADOR: todavía no puedes concluir. " + (" ".join(problemas) or "Falta la conclusión.")
        if accion == "abstenerse":
            return self._final("abstencion", razon=str(a.get("razon", "")).strip() or "Sin evidencia suficiente."), None
        return None, f"ERROR: acción desconocida {accion!r}."

    # -- ciclo -------------------------------------------------------------------------------
    def investigar(self, pregunta: str) -> dict:
        # La marca de corrida evita que Nightshift responda desde su caché con lo de una corrida anterior
        # (pasaba aunque cambiara el prompt): cada investigación es nueva.
        invalidas_seguidas = 0
        mensajes = [{"role": "system", "content": SISTEMA},
                    {"role": "user", "content": f"Pregunta: {pregunta}\n(corrida {self.traza.run_id})"}]
        while self.iteraciones < self.cfg.max_iteraciones:
            self.iteraciones += 1
            with Cronometro() as t:
                try:
                    r = self.llm.completar(mensajes)
                except SinMasRespuestas as e:
                    self.traza.evento("investigador", "modelo", "pensar", estado="omitido", salida=str(e))
                    return self._final("abstencion", razon=str(e))
                except Exception as e:  # timeout, Nightshift apagado, credenciales…
                    self.traza.evento("investigador", "modelo", "pensar", estado="error", salida=str(e), ms=t.ms)
                    self.fallo_modelo = True
                    return self._final("abstencion", razon=f"No pude hablar con el modelo: {e}")
            texto = r["texto"]
            mensajes.append({"role": "assistant", "content": texto})
            try:
                acciones = _extraer_acciones(texto)
                invalidas_seguidas = 0
            except ValueError as e:
                invalidas_seguidas += 1
                muestra = " ".join(texto.split())[:120] or "(vacía)"
                self.traza.evento("investigador", "modelo", "pensar", entrada=f"vuelta {self.iteraciones}",
                                  salida=f"respuesta inválida: {e} · recibí: {muestra}", estado="error", ms=t.ms)
                if invalidas_seguidas >= 3:
                    self.fallo_modelo = True
                    return self._final("abstencion", razon="El modelo respondió 3 veces seguidas algo que no es una "
                                                           "acción en JSON; corto para no gastar vueltas.")
                mensajes.append({"role": "user", "content": f"ERROR: {e}. Responde con UN objeto JSON con \"accion\"."})
                continue
            self.traza.evento("investigador", "modelo", "pensar", entrada=f"vuelta {self.iteraciones}",
                              salida=f"{' + '.join(str(a.get('accion')) for a in acciones)} · {r.get('modelo')}",
                              ms=t.ms)

            respuestas = []
            for a in acciones:
                final, respuesta = self._ejecutar(a)
                if final is not None:
                    return final
                respuestas.append(respuesta)
            devueltas = [r for r in respuestas if r.startswith(("ERROR", "EVALUADOR"))]
            if devueltas:
                self.traza.evento("investigador", "modelo", "devolver", estado="alerta",
                                  salida=" | ".join(devueltas))
            mensajes.append({"role": "user", "content": "\n".join(respuestas)})

        self.traza.evento("orquestador", "agente", "tope_iteraciones",
                          salida=f"se alcanzó AGENTE_MAX_ITERACIONES={self.cfg.max_iteraciones}", estado="alerta")
        return self._final("abstencion", razon=f"Se alcanzó el tope de {self.cfg.max_iteraciones} pasos sin una "
                                               "conclusión con evidencia aceptada.")

    def _final(self, estado, conclusion=None, recomendacion=None, razon=None):
        return {"estado": estado, "conclusion": conclusion, "recomendacion": recomendacion,
                "abstencion": {"razon": razon} if estado == "abstencion" else None,
                "hipotesis": list(self.hipotesis.values()), "evidencia": list(self.evidencia.values()),
                "iteraciones": self.iteraciones, "fallo_modelo": self.fallo_modelo}
