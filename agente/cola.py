"""Cola de aprobación (Paso 11): ninguna respuesta sale sin pasar por aquí, y aquí nada se envía.

Es una cola lógica (logs/cola_aprobacion.jsonl, un ítem por línea), sin pausas humanas mientras el agente
corre: una regla de política (politica_v1) aprueba o rechaza cada entrada y deja el motivo. "Enviar" es
marcar la respuesta como aprobada; no hay banco ni procesador de pagos conectado. Una persona revisa lo
aprobado antes de mandarlo, y lo rechazado queda para que lo decida ella.

Tipos de entrada:
- conclusion:       lo que concluyó la investigación (o la abstención).
- respuesta_banco:  el borrador de respuesta al banco de una disputa que vale pelear.
- no_pelear:        una disputa que no conviene pelear, con qué hacer en su lugar.
- grupo:            para un aumento: la causa y qué disputas del grupo no conviene pelear.

politica_v1, para respuesta_banco (todas tienen que cumplirse; si no, se rechaza con el motivo):
  1. evidencia_completa:  entrega confirmada con firma o foto y sin reclamo previo a soporte.
  2. disputa_abierta:     la disputa sigue esperando respuesta (estado needs_response).
  3. sin_senales_fraude:  0 señales de fraude. Con alguna, aunque io-engine diga que vale pelear, la decide
                          una persona: la política solo aprueba sola lo que no tiene dudas.
  4. monto_tope:          monto <= AGENTE_POLITICA_MONTO_MAX (500 USD); más que eso lo revisa una persona.
  5. evidencia_citada:    el borrador cita las evidencias (E#) de las que sale.
Las demás entradas no se envían a nadie (son el plan para la dueña): se aprueban si se apoyan en evidencia;
la conclusión se aprueba si el Evaluador la aceptó, y una abstención se rechaza porque no hay nada que entregar.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

POLITICA = "politica_v1"


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _si(valor) -> bool:
    return str(valor).strip().lower() in ("true", "1", "t", "si", "sí", "yes")


def _num(valor) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def monto_maximo() -> float:
    return float(os.getenv("AGENTE_POLITICA_MONTO_MAX", "500"))


def reglas(entrada: dict) -> list[dict]:
    """Cada regla con si se cumple y por qué. Solo aplica a respuesta_banco."""
    d, refs = entrada.get("datos") or {}, entrada.get("evidencia") or []
    senales = int(_num(d.get("senales_fraude")))
    tope = monto_maximo()
    return [
        {"regla": "evidencia_completa",
         "ok": _si(d.get("entrega_confirmada")) and d.get("prueba_entrega") in ("firma", "foto")
               and not _si(d.get("reclamo_previo")),
         "detalle": f"entrega confirmada={d.get('entrega_confirmada')}, prueba={d.get('prueba_entrega')}, "
                    f"reclamo previo={d.get('reclamo_previo')}"},
        {"regla": "disputa_abierta", "ok": d.get("estado") == "needs_response",
         "detalle": f"estado={d.get('estado')}"},
        {"regla": "sin_senales_fraude", "ok": senales == 0,
         "detalle": f"{senales} señal(es) de fraude"},
        {"regla": "monto_tope", "ok": _num(d.get("monto")) <= tope,
         "detalle": f"{_num(d.get('monto')):.2f} USD (tope {tope:g})"},
        {"regla": "evidencia_citada",
         "ok": bool(refs) and all(re.search(rf"\[{re.escape(r)}\]", entrada.get("borrador", "")) for r in refs),
         "detalle": f"cita {', '.join(refs) or 'nada'}"},
    ]


MOTIVO_RECHAZO = {
    "evidencia_completa": "falta evidencia: no hay entrega confirmada con prueba, o hubo reclamo previo",
    "disputa_abierta": "la disputa ya no espera respuesta",
    "sin_senales_fraude": "tiene señales de fraude: la decide una persona, no la regla",
    "monto_tope": "el monto supera el tope de la política: lo revisa una persona",
    "evidencia_citada": "el borrador no cita la evidencia de la que sale",
}


def decidir(entrada: dict) -> tuple[str, str, list[dict]]:
    """(estado, motivo, reglas) según politica_v1."""
    tipo = entrada["tipo"]
    if tipo == "respuesta_banco":
        rs = reglas(entrada)
        fallan = [r for r in rs if not r["ok"]]
        if fallan:
            return "rechazada", "; ".join(f"{MOTIVO_RECHAZO[r['regla']]} ({r['detalle']})" for r in fallan), rs
        return "aprobada", "cumple las 5 reglas de la política: queda lista para que una persona la envíe", rs
    if tipo == "conclusion":
        if entrada.get("estado_corrida") == "concluida":
            return "aprobada", "conclusión con evidencia, aceptada por el Evaluador", []
        return "rechazada", "la corrida se abstuvo: no hay conclusión que entregar", []
    if entrada.get("evidencia"):
        return "aprobada", "no se envía al banco: es el plan para la dueña, con su evidencia", []
    return "rechazada", "sin evidencia que lo respalde", []


class ColaAprobacion:
    def __init__(self, carpeta: Path):
        self.ruta = Path(carpeta) / "cola_aprobacion.jsonl"
        self.ruta.parent.mkdir(parents=True, exist_ok=True)

    def encolar(self, run_id: str, entrada: dict, n: int = 0) -> dict:
        estado, motivo, rs = decidir(entrada)
        sufijo = f"-{n}" if n else ""
        resumen = entrada.get("resumen") or (entrada.get("borrador") or "").splitlines()[0]
        item = {"item_id": f"AP-{run_id}{sufijo}", "run_id": run_id, "tipo": entrada["tipo"],
                "disputa_id": entrada.get("disputa_id"), "estado": estado, "creado_en": _ahora(),
                "decidido_en": _ahora(), "decidido_por": f"regla:{POLITICA}", "motivo": motivo,
                "reglas": rs, "evidencia": entrada.get("evidencia") or [], "resumen": resumen[:300],
                "borrador": entrada.get("borrador")}
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def leer(self) -> list[dict]:
        if not self.ruta.exists():
            return []
        return [json.loads(l) for l in self.ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
