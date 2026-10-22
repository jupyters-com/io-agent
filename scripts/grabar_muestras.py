"""Graba en samples/consultas.json las respuestas REALES de io-engine para el modo de muestra.

    # 1. en io-engine:      docker compose up --build
    # 2. en este repo:      python scripts/grabar_muestras.py

Cada consulta se manda a consultar(sql) por MCP y se guarda tal cual vuelve, con el motor que
respondió. Así SAMPLE_MODE=true repite datos reales sin necesitar el motor ni credenciales.
Nunca se escriben a mano.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from agente.datos import FuenteMotor, normalizar  # noqa: E402
from agente.orquestador import PANORAMA  # noqa: E402

URL = os.getenv("IO_MOTOR_URL", "http://localhost:8000/mcp")
SALIDA = RAIZ / "samples" / "consultas.json"

# Las consultas que el agente sabe hacer hoy. El Paso 10 agregará las del investigador.
CONSULTAS = [PANORAMA]

fuente = FuenteMotor(URL, timeout_s=90)
grabadas = {}
for sql in CONSULTAS:
    r = fuente.consultar(sql)
    if not r.get("ok"):
        sys.exit(f"io-engine falló con:\n{sql}\n{r.get('error')}")
    r.pop("ms", None)  # el tiempo no es parte del dato
    grabadas[normalizar(sql)] = r
    print(f"OK · {r['n_filas']} filas · motor={r['motor']} · {normalizar(sql)[:70]}…")

SALIDA.parent.mkdir(parents=True, exist_ok=True)
SALIDA.write_text(json.dumps({
    "_synthetic": True,
    "origen": f"io-engine en {URL}, grabado el {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
    "consultas": grabadas,
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n{len(grabadas)} consultas grabadas en {SALIDA.relative_to(RAIZ)}")
