"""La traza JSONL: un evento por línea, en logs/<run_id>.jsonl.

El esquema está fijado en contrato/traza.schema.json. Todos los agentes (orquestador,
investigador, evaluador y la cola) escriben aquí con el mismo formato.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

AGENTES = ("orquestador", "investigador", "evaluador", "cola")
ESTADOS = ("ok", "error", "alerta", "omitido")


def _resumen(valor, largo=300) -> str:
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, default=str)
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


class Traza:
    def __init__(self, run_id: str, carpeta: Path):
        self.run_id = run_id
        self.ruta = Path(carpeta) / f"{run_id}.jsonl"
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.paso = 0

    def evento(self, agente, destino, accion, entrada="", salida="", estado="ok", reintentos=0, ms=0.0):
        if agente not in AGENTES or estado not in ESTADOS:
            raise ValueError(f"evento inválido: agente={agente} estado={estado}")
        self.paso += 1
        registro = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "paso": self.paso,
            "agente": agente,
            "destino": destino,
            "accion": accion,
            "entrada": _resumen(entrada),
            "salida": _resumen(salida),
            "estado": estado,
            "reintentos": int(reintentos),
            "ms": round(float(ms), 1),
        }
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        return registro


class Cronometro:
    def __enter__(self):
        self.inicio = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.ms = (time.perf_counter() - self.inicio) * 1000
