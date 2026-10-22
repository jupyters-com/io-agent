"""Graba corridas REALES de los tres ejemplos para que el modo de muestra las repita.

Antes:
  1. io-engine levantado:            docker compose up --build   (en el repo io-engine)
  2. Nightshift abierto, con un lane Nemotron y el Runtime activo
  3. .env.local con METERLESS_BASE_URL, METERLESS_RUNTIME_TOKEN y METERLESS_MODEL

    python scripts/grabar_corridas.py              # los tres casos
    python scripts/grabar_corridas.py caso3        # uno solo

Cada corrida queda en samples/corridas/<pregunta>.json (las respuestas del modelo y las filas de
io-engine, tal cual). Después regenera ejemplos/*_salida.* en modo de muestra a partir de ellas.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)
os.environ["SAMPLE_MODE"] = "false"
os.environ["AGENTE_GRABAR"] = "true"

from agente.orquestador import correr  # noqa: E402

casos = sys.argv[1:] or ["caso1", "caso2", "caso3"]
for caso in casos:
    pregunta = json.loads((RAIZ / "ejemplos" / f"{caso}_entrada.json").read_text(encoding="utf-8"))["pregunta"]
    print(f"\n=== {caso}: {pregunta}")
    r = correr(pregunta)
    print(f"    {r['estado']} · {r['metricas']['iteraciones']} vueltas · {r['metricas']['consultas']} consultas · "
          f"{r['metricas']['ms'] / 1000:.0f} s · traza logs/{r['run_id']}.jsonl")
    for h in r["hipotesis"]:
        print(f"    {h['id']} {h['veredicto']:<11} {h['enunciado']}  [{', '.join(h['evidencia'])}]")
    print("    →", r["conclusion"] or r["abstencion"]["razon"])
    if r["estado"] != "concluida":
        print("    (si ya había una corrida concluida grabada para este caso, se conserva)")

print("\nRegenerando los ejemplos en modo de muestra a partir de las corridas grabadas…")
subprocess.run([sys.executable, "scripts/generar_ejemplos.py"], check=True,
               env={**os.environ, "SAMPLE_MODE": "true", "AGENTE_GRABAR": ""})
