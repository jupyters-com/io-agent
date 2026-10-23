"""Medición del agente con y sin la capa de IO sobre el set de prueba ([Challenge] JPTRS-77 y JPTRS-78).

- El set (evaluacion/set_prueba.csv) sale de los datos sintéticos con la definición del esquema canónico
  (vale_pelear, razon_decision, causa_operativa): una fila por disputa, con su respuesta esperada y su razón.
- Cada disputa se le pregunta al agente ("¿Vale la pena pelear la disputa …?") con la capa encendida y apagada.
- La respuesta del agente se clasifica en pelear / no_pelear / abstencion a partir de su conclusión, y se compara
  con la esperada. Se cuentan aciertos, defensas que no debían armarse (dice pelear y no convenía), defensas
  perdidas (dice no pelear y convenía) y abstenciones con su razón.
"""

import csv
import re
from pathlib import Path

ESPERADAS = ("vale la pena pelear", "no vale la pena", "causa operativa")
RAZON = {
    "entrega_confirmada_sin_reclamo": "entrega confirmada con prueba, sin reclamo previo y menos de 2 señales de fraude",
    "reclamo_previo": "el cliente reclamó a soporte por ese pedido antes de abrir la disputa",
    "sin_entrega": "el pedido no llegó",
    "sin_prueba_de_entrega": "no hay prueba de entrega",
    "sospecha_de_fraude": "2 o más señales de fraude",
}
LIMITE = {
    "reclamo_previo": "sin la capa, el reclamo está en soporte con el pedido como '#1574' y el cliente por correo: "
                      "si no lo cruza, defendería una disputa que no conviene",
    "sospecha_de_fraude": "el pedido sí se entregó: sin la definición de señales de fraude, podría defenderla",
    "entrega_confirmada_sin_reclamo": "sin la capa, el envío está con el pedido como '1574' y no 'ORD-1574': si no "
                                      "lo cruza, creería que no hubo entrega y no la defendería",
}

# Cómo dice el agente su decisión en la conclusión (en español simple, por el Evaluador).
NO = re.compile(r"\bno\s+(?:vale\s+la\s+pena|conviene|se\s+debe|debe|hay\s+que)\s+(?:pelear|disputar|defender)"
                r"|\bno\s+(?:se\s+puede|es\s+posible|tiene\s+sentido)\s+(?:pelear|disputar|defender)"
                r"|\bno\s+pelear\b|\bno\s+pelearla\b|\baceptar\s+(?:la|esta)\s+disputa\b|\breembolsar\b", re.I)
SI = re.compile(r"\b(?:s[ií],?\s+)?vale\s+la\s+pena\s+(?:pelear|pelearla|disputar)|\bconviene\s+pelear|"
                r"\bpelear\s+(?:la|esta)\s+disputa\b|\bpelearla\b", re.I)


# "No hubo entrega" dicho de una disputa cuyo pedido sí se entregó con prueba: acertar por la razón equivocada.
SIN_ENTREGA = re.compile(r"no\s+(?:existe|hay|tiene)\s+(?:ninguna\s+)?(?:prueba|evidencia|registro)\s+de\s+(?:la\s+)?entrega"
                         r"|no\s+se\s+(?:entreg|pudo\s+(?:demostrar|confirmar))|no\s+lleg[óo]|nunca\s+lleg", re.I)


def esperada(fila: dict) -> str:
    if _si(fila["vale_pelear"]):
        return "vale la pena pelear"
    return "causa operativa" if _si(fila.get("causa_operativa")) else "no vale la pena"


def decision_esperada(esperada_txt: str) -> str:
    return "pelear" if esperada_txt == "vale la pena pelear" else "no_pelear"


def clasificar(respuesta: dict) -> str:
    """pelear / no_pelear / abstencion / sin_clasificar, según la conclusión del agente (lo primero que dice)."""
    if respuesta.get("estado") != "concluida":
        return "abstencion"
    texto = " ".join(str(respuesta.get("conclusion") or "").split())
    no, si = NO.search(texto), SI.search(texto)
    if no and (not si or no.start() <= si.start()):
        return "no_pelear"
    if si:
        return "pelear"
    return "sin_clasificar"


def _si(valor) -> bool:
    return str(valor).strip().lower() in ("true", "1", "t", "si", "sí", "yes")


def filas_del_set(filas_motor: list[dict]) -> list[dict]:
    salida = []
    for f in sorted(filas_motor, key=lambda f: f["disputa_id"]):
        esp = esperada(f)
        razon = RAZON.get(f["razon_decision"], f["razon_decision"])
        if esp == "causa operativa":
            razon += f"; además está en una zona con atrasos ({f.get('transportista')} · {f.get('region')})"
        salida.append({"disputa_id": f["disputa_id"], "esperada": esp, "razon": razon,
                       "razon_decision": f["razon_decision"], "motivo": f.get("motivo"), "estado": f.get("estado"),
                       "monto": f.get("monto"), "entrega_confirmada": _si(f.get("entrega_confirmada")),
                       "caso_limite": LIMITE.get(f["razon_decision"], "")})
    return salida


def leer_set(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir_set(ruta: Path, filas: list[dict]):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def puntuar(caso: dict, respuesta: dict | None) -> dict:
    """Una fila de resultado: qué dijo el agente y qué tipo de acierto o error es."""
    if respuesta is None:
        return {"dijo": "pendiente", "resultado": "pendiente"}
    dijo = clasificar(respuesta)
    esperado = decision_esperada(caso["esperada"])
    if dijo == "abstencion":
        resultado = "abstención"
    elif dijo == "sin_clasificar":
        resultado = "sin clasificar"
    elif dijo == esperado and _si(caso.get("entrega_confirmada")) and SIN_ENTREGA.search(str(respuesta.get("conclusion"))):
        resultado = "acierto con una razón falsa"
    elif dijo == esperado:
        resultado = "acierto"
    elif dijo == "pelear":
        resultado = "defensa que no debía armarse"
    else:
        resultado = "defensa perdida"
    razon = (respuesta.get("abstencion") or {}).get("razon") if dijo == "abstencion" else respuesta.get("conclusion")
    return {"dijo": dijo, "resultado": resultado, "detalle": " ".join(str(razon or "").split())[:200],
            "run_id": respuesta.get("run_id")}


def resumen(resultados: list[dict]) -> dict:
    cuenta = {k: 0 for k in ("acierto", "acierto con una razón falsa", "defensa que no debía armarse",
                             "defensa perdida", "abstención", "sin clasificar", "pendiente")}
    for r in resultados:
        cuenta[r["resultado"]] = cuenta.get(r["resultado"], 0) + 1
    medidos = len(resultados) - cuenta["pendiente"]
    cuenta["medidos"] = medidos
    cuenta["tasa_acierto"] = round(100 * cuenta["acierto"] / medidos, 1) if medidos else 0.0
    # la decisión correcta, aunque sea por la razón equivocada
    cuenta["tasa_decision"] = round(100 * (cuenta["acierto"] + cuenta["acierto con una razón falsa"]) / medidos, 1) \
        if medidos else 0.0
    return cuenta
