"""De dónde saca datos el agente: SIEMPRE a través de consultar(sql) del motor io-engine.

- FuenteMuestra (SAMPLE_MODE=true): respuestas reales de io-engine grabadas (samples/consultas.json
  y las consultas de cada corrida grabada en samples/corridas/). No necesita el motor.
- FuenteMotor (SAMPLE_MODE=false): llama a consultar(sql) por MCP en IO_MOTOR_URL.
- FuenteGrabadora: envuelve a FuenteMotor y guarda cada respuesta, para crear las grabaciones.

Todas devuelven lo mismo que consultar(sql): {"ok", "columnas", "filas", "n_filas", "motor", ...}.
"""

import asyncio
import json
import re
from pathlib import Path


def normalizar(sql: str) -> str:
    return " ".join(sql.split()).rstrip(";").strip()


class FuenteMuestra:
    nombre = "muestra"

    def __init__(self, ruta: Path, extra: dict | None = None):
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        self.origen = datos.get("origen", "")
        self.consultas = {normalizar(k): v for k, v in datos["consultas"].items()}
        self.consultas.update({normalizar(k): v for k, v in (extra or {}).items()})

    def consultar(self, sql: str) -> dict:
        grabada = self.consultas.get(normalizar(sql))
        if grabada is None:
            return {"ok": False, "motor": None, "filas": [], "n_filas": 0,
                    "error": "Consulta fuera de la muestra: no está grabada en samples/."}
        return dict(grabada)


class FuenteMotor:
    nombre = "io-engine"

    def __init__(self, url: str, timeout_s: float):
        self.url, self.timeout_s = url, timeout_s

    async def _llamar(self, sql: str) -> dict:
        from mcp.client.client import Client
        async with Client(self.url, read_timeout_seconds=self.timeout_s) as cliente:
            r = await cliente.call_tool("consultar", {"sql": sql})
            datos = r.structured_content or json.loads(r.content[0].text)
            return datos.get("result", datos)

    def consultar(self, sql: str) -> dict:
        try:
            return asyncio.run(asyncio.wait_for(self._llamar(sql), timeout=self.timeout_s))
        except (asyncio.TimeoutError, TimeoutError):
            raise TimeoutError(f"io-engine no respondió en {self.timeout_s:g} s")
        except Exception as e:  # sin conexión, motor apagado, etc.
            raise ConnectionError(f"No se pudo hablar con io-engine en {self.url}: {e}") from e


class FuenteGrabadora:
    def __init__(self, fuente):
        self.fuente, self.consultas = fuente, {}
        self.nombre = fuente.nombre

    def consultar(self, sql: str) -> dict:
        r = self.fuente.consultar(sql)
        grabada = {k: v for k, v in r.items() if k != "ms"}
        self.consultas[normalizar(sql)] = grabada
        return r


class FuenteCompletadora:
    """Modo de muestra que completa lo que falta: si una consulta no está grabada, se la pide a io-engine y la
    agrega a samples/consultas.json. Solo con AGENTE_COMPLETAR_MUESTRAS=true (scripts/completar_muestras.py),
    para las consultas que el agente arma solo (la cola), sin volver a llamar al modelo."""

    nombre = "muestra"

    def __init__(self, cfg, extra=None):
        self.muestra, self.ruta = FuenteMuestra(cfg.muestras, extra), Path(cfg.muestras)
        self.motor = FuenteMotor(cfg.motor_url, cfg.timeout_s)
        self.nuevas: list[str] = []

    def consultar(self, sql: str) -> dict:
        r = self.muestra.consultar(sql)
        if r.get("ok") or "fuera de la muestra" not in str(r.get("error")):
            return r
        r = self.motor.consultar(sql)
        if r.get("ok"):
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            datos["consultas"][normalizar(sql)] = {k: v for k, v in r.items() if k != "ms"}
            self.ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
            self.muestra.consultas[normalizar(sql)] = r
            self.nuevas.append(normalizar(sql))
        return r


CAPA_DE_IO = re.compile(r"\b(canonico|mapeo|origen)\s*\.", re.I)


class SoloCrudo:
    """SEMANTIC_LAYER=off: la capa de IO no existe para el agente. Si una consulta toca canonico, mapeo u origen
    (aunque el modelo los conozca de otro lado), no se ejecuta: solo quedan las tablas crudas."""

    def __init__(self, fuente):
        self.fuente, self.nombre = fuente, fuente.nombre
        self.consultas = getattr(fuente, "consultas", {})

    def consultar(self, sql: str) -> dict:
        m = CAPA_DE_IO.search(sql)
        if m:
            return {"ok": False, "motor": None, "filas": [], "n_filas": 0,
                    "error": f"SEMANTIC_LAYER=off: el esquema {m.group(1).lower()} es la capa de IO y está apagada. "
                             "Solo existen las tablas crudas (crudo.*)."}
        return self.fuente.consultar(sql)


def crear(cfg, extra: dict | None = None):
    import os
    if cfg.modo_muestra and os.getenv("AGENTE_COMPLETAR_MUESTRAS", "").lower() in ("1", "true", "si", "sí"):
        return FuenteCompletadora(cfg, extra)
    if cfg.modo_muestra:
        return FuenteMuestra(cfg.muestras, extra)
    return FuenteMotor(cfg.motor_url, cfg.timeout_s)
