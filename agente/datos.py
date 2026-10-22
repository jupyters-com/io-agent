"""De dónde saca datos el agente: SIEMPRE a través de consultar(sql) del motor io-engine.

- FuenteMuestra (SAMPLE_MODE=true): respuestas de io-engine grabadas en samples/consultas.json
  por scripts/grabar_muestras.py. No necesita el motor ni credenciales.
- FuenteMotor (SAMPLE_MODE=false): llama a consultar(sql) por MCP en IO_MOTOR_URL.

Las dos devuelven lo mismo que consultar(sql): {"ok", "columnas", "filas", "n_filas", "motor", ...}.
"""

import asyncio
import json
from pathlib import Path


def normalizar(sql: str) -> str:
    return " ".join(sql.split()).rstrip(";").strip()


class FuenteMuestra:
    nombre = "muestra"

    def __init__(self, ruta: Path):
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        self.origen = datos.get("origen", "")
        self.consultas = {normalizar(k): v for k, v in datos["consultas"].items()}

    def consultar(self, sql: str) -> dict:
        grabada = self.consultas.get(normalizar(sql))
        if grabada is None:
            return {"ok": False, "motor": None, "filas": [], "n_filas": 0,
                    "error": "Consulta fuera de la muestra: no está grabada en samples/consultas.json."}
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


def crear(cfg):
    return FuenteMuestra(cfg.muestras) if cfg.modo_muestra else FuenteMotor(cfg.motor_url, cfg.timeout_s)
