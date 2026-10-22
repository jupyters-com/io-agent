"""Configuración del agente. Todo sale de variables de entorno (y de .env.local, si existe).

.env.local nunca se sube al repo. En modo de muestra no hace falta ninguna clave.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _cargar_env_local(ruta: Path = RAIZ / ".env.local"):
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def _si(valor: str) -> bool:
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes")


@dataclass(frozen=True)
class Config:
    modo_muestra: bool
    motor_url: str            # io-engine por MCP (solo modo real)
    muestras: Path            # resultados grabados de io-engine (modo de muestra)
    logs: Path                # trazas JSONL y cola de aprobación
    salidas: Path             # respuesta JSON + informe Markdown de cada corrida
    timeout_s: float          # tope de cada llamada externa
    max_iteraciones: int      # tope de pasos por corrida
    presupuesto_usd: float    # alerta de gasto en el proveedor del modelo
    meterless_url: str
    meterless_token: str
    meterless_modelo: str
    meterless_extra: dict     # campos extra para el pedido al modelo (p. ej. apagar el "pensamiento")
    sin_pensar: bool          # antepone /no_think al prompt de sistema (modelos Nemotron con razonamiento)
    stream: bool              # pide la respuesta por partes (evita cortes por tiempo en respuestas largas)
    reintentos_modelo: int    # reintentos por llamada al modelo si Nightshift corta o falla

    @property
    def modo(self) -> str:
        return "muestra" if self.modo_muestra else "real"


def cargar() -> Config:
    _cargar_env_local()
    return Config(
        modo_muestra=_si(os.getenv("SAMPLE_MODE", "true")),
        motor_url=os.getenv("IO_MOTOR_URL", "http://localhost:8000/mcp"),
        muestras=Path(os.getenv("AGENTE_MUESTRAS", RAIZ / "samples" / "consultas.json")),
        logs=Path(os.getenv("AGENTE_LOGS", RAIZ / "logs")),
        salidas=Path(os.getenv("AGENTE_SALIDAS", RAIZ / "salidas")),
        timeout_s=float(os.getenv("AGENTE_TIMEOUT_S", "60")),
        max_iteraciones=int(os.getenv("AGENTE_MAX_ITERACIONES", "16")),
        presupuesto_usd=float(os.getenv("AGENTE_PRESUPUESTO_USD", "1.0")),
        meterless_url=os.getenv("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/"),
        meterless_token=os.getenv("METERLESS_RUNTIME_TOKEN", ""),
        meterless_modelo=os.getenv("METERLESS_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b"),
        meterless_extra=json.loads(os.getenv("METERLESS_EXTRA_BODY", "") or "{}"),
        sin_pensar=_si(os.getenv("AGENTE_SIN_PENSAR", "false")),
        stream=_si(os.getenv("METERLESS_STREAM", "false")),
        reintentos_modelo=int(os.getenv("AGENTE_REINTENTOS_MODELO", "2")),
    )
