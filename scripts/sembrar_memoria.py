"""Siembra la memoria real del agente (memoria/) con lo que enseñan las corridas ya grabadas SIN memoria.

    python scripts/sembrar_memoria.py

Repite en modo de muestra, en orden, las corridas grabadas de los tres ejemplos (las normales, no las
-hmem). H-MEM aprende de cada una lo mismo que habría aprendido en vivo: las lecciones de cada
devolución del Evaluador y los hallazgos de cada conclusión. No llama al modelo ni a io-engine.

Después, con Nightshift e io-engine levantados:  python scripts/grabar_corridas.py
(esas corridas ya arrancan con memoria y se graban como <pregunta>-hmem.json).
"""

import json
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)
os.environ.update(SAMPLE_MODE="true", AGENTE_HMEM="true", AGENTE_MEMORIA=str(RAIZ / "memoria"),
                  AGENTE_MEMORIA_SEMILLA="", AGENTE_GRABAR="")

from agente import orquestador as orq  # noqa: E402

if (RAIZ / "memoria").exists():
    if input("memoria/ ya existe. ¿La borro y siembro de nuevo? [s/N] ").strip().lower() not in ("s", "si", "sí"):
        sys.exit("Nada que hacer.")
    shutil.rmtree(RAIZ / "memoria")

normal = orq.corrida_grabada
orq.corrida_grabada = lambda cfg, pregunta, con_memoria=False: normal(cfg, pregunta, con_memoria=False)

for entrada in sorted((RAIZ / "ejemplos").glob("*_entrada.json")):
    caso = entrada.name.removesuffix("_entrada.json")
    pregunta = json.loads(entrada.read_text(encoding="utf-8"))["pregunta"]
    r = orq.correr(pregunta)
    print(f"{caso}: {r['estado']} · {r['metricas']['devoluciones']} devoluciones · traza logs/{r['run_id']}.jsonl")

registros = json.loads((RAIZ / "memoria" / "memorias.json").read_text(encoding="utf-8"))["records"]
print(f"\nmemoria/ quedó con {len(registros)} memorias:")
for m in registros:
    print(f"  {m['id']:<7} {m['type']:<10} {m['content'][:95]}")
