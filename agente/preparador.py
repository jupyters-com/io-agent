"""Después de investigar: separar las disputas que vale la pena pelear y redactar sus respuestas (Paso 11).

El agente prepara y no decide. Con la conclusión aceptada por el Evaluador:

1. Delimita las disputas de las que habla la pregunta:
   - si la pregunta nombra disputas (du_…), esas;
   - si es por un grupo (un aumento), las del transportista y la región que el World Model ancló en la
     conclusión, en el período de la pregunta ("segunda quincena de septiembre de 2026"). Sin World Model no
     se puede delimitar el grupo con evidencia, y la cola lo dice.
2. Trae sus datos con consultar(sql), como cualquier otra evidencia (E#): la fila de cada disputa y los
   mensajes de soporte de sus pedidos.
3. Separa con la decisión de io-engine (vale_pelear, razon_decision) y redacta:
   - una respuesta al banco por cada disputa que vale pelear, con la evidencia (entrega, historial, soporte);
   - una entrada "no pelear" por cada disputa que no conviene pelear (cuando la pregunta es por disputas);
   - para un grupo, una entrada que explica la causa y qué disputas del grupo no conviene pelear.
Los borradores salen de los datos, con plantilla: nada que no esté en una fila. No envían nada, no
opinan de leyes ni de las reglas de las redes de tarjetas: una persona revisa y decide.
"""

import re
import unicodedata
from datetime import date

ID_DISPUTA = re.compile(r"\bdu_[A-Za-z0-9]+\b")
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                     "septiembre", "octubre", "noviembre", "diciembre"], start=1)}
COLUMNAS = ("disputa_id, pedido_id, cliente_id, motivo, estado, monto, abierta_en, vence_en, transportista, "
            "region, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, reclamo_previo, "
            "pedidos_previos, disputas_previas, senales_fraude, vale_pelear, razon_decision")
MOTIVO = {"fraudulent": "el titular dice no haber hecho la compra", "product_not_received": "producto no recibido",
          "unrecognized": "cargo no reconocido"}
RAZON = {
    "entrega_confirmada_sin_reclamo": "entrega confirmada y sin reclamo previo",
    "reclamo_previo": "el cliente ya había reclamado a soporte por ese pedido",
    "sin_entrega": "el pedido no llegó",
    "sin_prueba_de_entrega": "no hay prueba de entrega",
    "sospecha_de_fraude": "hay 2 o más señales de fraude",
}
QUE_HACER = {
    "reclamo_previo": "resolver con el cliente (contactarlo, ofrecer una solución y pedirle que retire la disputa)",
    "sin_entrega": "no pelear y reembolsar",
    "sin_prueba_de_entrega": "resolver con el cliente: sin prueba de entrega no hay con qué pelear",
    "sospecha_de_fraude": "no pelear: aceptar la disputa y marcar al cliente",
}
PRUEBA = {"firma": "firma de quien recibió", "foto": "foto de la entrega"}


def normalizar(texto) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto or "").lower()) if not unicodedata.combining(c))


def periodo(pregunta: str):
    """("2026-09-16", "2026-10-01", "la segunda quincena de septiembre de 2026") o None."""
    texto = pregunta.lower()
    m = re.search(r"(primera|segunda)\s+quincena\s+de\s+([a-z]+)\s+de\s+(\d{4})", texto)
    if m and m.group(2) in MESES:
        mes, anio = MESES[m.group(2)], int(m.group(3))
        if m.group(1) == "primera":
            return date(anio, mes, 1).isoformat(), date(anio, mes, 16).isoformat(), m.group(0)
        fin = date(anio + (mes == 12), 1 if mes == 12 else mes + 1, 1)
        return date(anio, mes, 16).isoformat(), fin.isoformat(), m.group(0)
    m = re.search(r"\b([a-z]+)\s+de\s+(\d{4})", texto)
    if m and m.group(1) in MESES:
        mes, anio = MESES[m.group(1)], int(m.group(2))
        fin = date(anio + (mes == 12), 1 if mes == 12 else mes + 1, 1)
        return date(anio, mes, 1).isoformat(), fin.isoformat(), m.group(0)
    return None


def _texto_sql(valor: str) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def sql_disputas(ids=None, transportista=None, region=None, desde=None, hasta=None) -> str:
    condiciones = []
    if ids:
        condiciones.append(f"disputa_id IN ({', '.join(_texto_sql(i) for i in ids)})")
    if transportista:
        condiciones.append(f"transportista = {_texto_sql(transportista)}")
    if region:
        condiciones.append(f"region = {_texto_sql(region)}")
    if desde:
        condiciones.append(f"abierta_en >= TIMESTAMP '{desde} 00:00:00'")
    if hasta:
        condiciones.append(f"abierta_en < TIMESTAMP '{hasta} 00:00:00'")
    return f"SELECT {COLUMNAS} FROM canonico.disputas WHERE {' AND '.join(condiciones)} ORDER BY disputa_id"


def sql_soporte(pedidos: list[str]) -> str:
    return ("SELECT pedido_id, creado_en, categoria, texto FROM canonico.mensajes_soporte "
            f"WHERE pedido_id IN ({', '.join(_texto_sql(p) for p in pedidos)}) ORDER BY pedido_id, creado_en")


def _si(valor) -> bool:
    return str(valor).strip().lower() in ("true", "1", "t", "si", "sí", "yes")


def _num(valor, defecto=0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def _fecha(valor) -> str:
    return str(valor or "")[:10] or "sin fecha"


def _monto(valor) -> str:
    return f"{_num(valor):,.2f} USD"


def borrador_banco(d: dict, mensajes: list[dict], e_disputa: str, e_soporte: str | None) -> str:
    """La respuesta al banco de una disputa que vale pelear, solo con lo que dicen las filas."""
    previos, disputas_prev, senales = int(_num(d.get("pedidos_previos"))), int(_num(d.get("disputas_previas"))), \
        int(_num(d.get("senales_fraude")))
    if mensajes:
        veces = "1 vez" if len(mensajes) == 1 else f"{len(mensajes)} veces"
        soporte = (f"el cliente escribió {veces} a soporte sobre este pedido, pero no reclamó antes de "
                   f"abrir la disputa ({', '.join(_fecha(m.get('creado_en')) for m in mensajes)}). [{e_soporte}]")
    else:
        soporte = ("el cliente no escribió a soporte sobre este pedido." + (f" [{e_soporte}]" if e_soporte else ""))
    return "\n".join([
        f"Respuesta a la disputa {d['disputa_id']} · {MOTIVO.get(d.get('motivo'), d.get('motivo'))} · "
        f"{_monto(d.get('monto'))} · abierta el {_fecha(d.get('abierta_en'))} · vence el {_fecha(d.get('vence_en'))}",
        "",
        "Solicitamos que se mantenga el cargo. Evidencia:",
        f"- Entrega: el pedido {d.get('pedido_id')} se entregó el {_fecha(d.get('entregado_en'))} con "
        f"{d.get('transportista')} ({d.get('region')}), con {PRUEBA.get(d.get('prueba_entrega'), 'prueba de entrega')}. "
        f"[{e_disputa}]",
        f"- Historial del cliente: " + (f"{_cuantas(previos, 'pedido anterior', 'pedidos anteriores')}"
                                         if previos else "es su primer pedido")
        + f" y {_cuantas(disputas_prev, 'disputa previa', 'disputas previas') if disputas_prev else 'ninguna disputa previa'}."
        f" [{e_disputa}]",
        f"- Soporte: {soporte}",
        f"- Señales de fraude: {senales} de 4 (cliente nuevo, riesgo alto, país de la IP distinto, punto de retiro). "
        f"[{e_disputa}]",
        "",
        f"Adjuntar: comprobante de entrega ({PRUEBA.get(d.get('prueba_entrega'), 'prueba')}) y el historial de "
        "comunicaciones con el cliente.",
        "Borrador preparado por IO con datos de io-engine. Lo revisa y lo envía una persona.",
    ])


def nota_no_pelear(d: dict, e_disputa: str) -> str:
    razon = d.get("razon_decision")
    return (f"Disputa {d['disputa_id']} · {_monto(d.get('monto'))}: no conviene pelearla porque "
            f"{RAZON.get(razon, razon)}. Qué hacer: {QUE_HACER.get(razon, 'revisarla con una persona')}. [{e_disputa}]")


def _cuantas(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def nota_grupo(conclusion: str, descripcion: str, disputas: list[dict], e_disputa: str,
               fuera: list[dict] | None = None, periodo_txt: str = "") -> str:
    pelear = [d for d in disputas if _si(d.get("vale_pelear"))]
    no = [d for d in disputas if not _si(d.get("vale_pelear"))]
    lineas = [f"Causa encontrada: {conclusion}", "",
              f"De las {len(disputas)} disputas de {descripcion}: "
              f"{_cuantas(len(pelear), 'vale', 'valen')} la pena pelear (tiene{'n' if len(pelear) != 1 else ''} su "
              f"respuesta en esta cola) y {len(no)} no conviene pelear. [{e_disputa}]"]
    por_razon: dict[str, list[dict]] = {}
    for d in no:
        por_razon.setdefault(d.get("razon_decision") or "sin_razon", []).append(d)
    for razon, grupo in sorted(por_razon.items(), key=lambda kv: -len(kv[1])):
        lineas.append(f"- {len(grupo)} porque {RAZON.get(razon, razon)} → {QUE_HACER.get(razon, 'revisar')}: "
                      + ", ".join(d["disputa_id"] for d in grupo))
    if fuera:
        fuera_pelear = [d for d in fuera if _si(d.get("vale_pelear"))]
        lineas += ["", f"Fuera de ese grupo hay {_cuantas(len(fuera), 'disputa más', 'disputas más')} en {periodo_txt}, "
                       f"sin la misma causa: {_cuantas(len(fuera_pelear), 'vale', 'valen')} la pena pelear (también "
                       f"con su respuesta en esta cola) y {len(fuera) - len(fuera_pelear)} no. [{e_disputa}]"]
        for d in fuera:
            if not _si(d.get("vale_pelear")):
                razon = d.get("razon_decision")
                lineas.append(f"- {d['disputa_id']}: {RAZON.get(razon, razon)} → {QUE_HACER.get(razon, 'revisar')}")
    return "\n".join(lineas)


class Preparador:
    """Arma las entradas de la cola a partir de la investigación. Las consultas quedan como evidencia."""

    def __init__(self, consultar_evidencia, traza):
        self.consultar_evidencia = consultar_evidencia  # sql -> evidencia {"id", "ok", "filas", ...}
        self.traza = traza

    def preparar(self, pregunta: str, resultado: dict, anclas: dict, mundo_activo: bool) -> list[dict]:
        if resultado["estado"] != "concluida":
            return []
        ids = list(dict.fromkeys(ID_DISPUTA.findall(pregunta)))
        grupo = None
        if ids:
            sql = sql_disputas(ids=ids)
        else:
            transportistas, regiones = anclas.get("transportista", []), anclas.get("region", [])
            if not mundo_activo or not transportistas:
                motivo = ("el World Model está apagado" if not mundo_activo else
                          "la conclusión no nombra un transportista anclado a la evidencia")
                self.traza.evento("cola", "io-engine.consultar", "preparar", estado="omitido",
                                  salida=f"no se puede delimitar el grupo: {motivo}")
                return [{"tipo": "grupo", "disputa_id": None, "evidencia": [], "datos": {},
                         "borrador": f"Causa encontrada: {resultado['conclusion']}\n\nNo se pudo delimitar qué disputas "
                                     f"son del grupo ({motivo}), así que no se prepara ninguna respuesta."}]
            p = periodo(pregunta)
            grupo = {"transportista": transportistas[0], "region": regiones[0] if regiones else None,
                     "periodo": f"la {p[2]}" if p and "quincena" in p[2] else (p[2] if p else ""),
                     "descripcion": " · ".join(x for x in (transportistas[0], regiones[0] if regiones else "") if x)}
            if p:
                grupo["descripcion"] += f" en {grupo['periodo']}"
                # Todo el período de la pregunta: el grupo explica la causa, pero cada disputa del período que
                # vale pelear tiene que tener su respuesta, sea o no del grupo.
                sql = sql_disputas(desde=p[0], hasta=p[1])
            else:
                sql = sql_disputas(transportista=grupo["transportista"], region=grupo["region"])
        e = self.consultar_evidencia(sql)
        if not e["ok"] or not e["filas"] or "disputa_id" not in e["filas"][0]:
            self.traza.evento("cola", "io-engine.consultar", "preparar", estado="error",
                              salida=f"{e['id']}: no se pudieron traer las disputas ({e.get('error') or '0 filas'})")
            return []
        disputas = e["filas"]
        pelear = [d for d in disputas if _si(d.get("vale_pelear"))]
        mensajes, e_soporte = {}, None
        if pelear:
            s = self.consultar_evidencia(sql_soporte([d["pedido_id"] for d in pelear]))
            if s["ok"]:
                e_soporte = s["id"]
                for m in s["filas"]:
                    mensajes.setdefault(m["pedido_id"], []).append(m)
        self.traza.evento("cola", "agente", "preparar", entrada=sql,
                          salida=f"{len(disputas)} disputas · {len(pelear)} vale pelear · "
                                 f"{len(disputas) - len(pelear)} no conviene · evidencia {e['id']}"
                                 + (f", {e_soporte}" if e_soporte else ""))
        entradas = []
        if grupo:
            def es_del_grupo(d):
                return (normalizar(d.get("transportista")) == normalizar(grupo["transportista"])
                        and (grupo["region"] is None or normalizar(d.get("region")) == normalizar(grupo["region"])))
            del_grupo = [d for d in disputas if es_del_grupo(d)]
            fuera = [d for d in disputas if not es_del_grupo(d)]
            entradas.append({"tipo": "grupo", "disputa_id": None, "evidencia": [e["id"]],
                             "datos": {"disputas": len(del_grupo), "fuera": len(fuera), "vale_pelear": len(pelear)},
                             "borrador": nota_grupo(resultado["conclusion"], grupo["descripcion"], del_grupo, e["id"],
                                                    fuera, grupo["periodo"])})
        for d in disputas:
            if _si(d.get("vale_pelear")):
                refs = [e["id"]] + ([e_soporte] if e_soporte else [])
                entradas.append({"tipo": "respuesta_banco", "disputa_id": d["disputa_id"], "evidencia": refs,
                                 "datos": d, "borrador": borrador_banco(d, mensajes.get(d["pedido_id"], []), e["id"],
                                                                        e_soporte)})
            elif not grupo:
                entradas.append({"tipo": "no_pelear", "disputa_id": d["disputa_id"], "evidencia": [e["id"]],
                                 "datos": d, "borrador": nota_no_pelear(d, e["id"])})
        return entradas
