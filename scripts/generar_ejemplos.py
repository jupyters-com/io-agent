"""Corre el agente con las tres entradas de ejemplos/ y guarda sus salidas al lado.

    python scripts/generar_ejemplos.py

Las salidas (ejemplos/*_salida.json y .md) salen de corridas reales del agente, nunca a mano.
Se vuelven a generar cada vez que cambia el agente.
"""

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from agente.orquestador import correr  # noqa: E402

for entrada in sorted((RAIZ / "ejemplos").glob("*_entrada.json")):
    caso = entrada.name.removesuffix("_entrada.json")
    pregunta = json.loads(entrada.read_text(encoding="utf-8"))["pregunta"]
    r = correr(pregunta)
    (RAIZ / "ejemplos" / f"{caso}_salida.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RAIZ / "ejemplos" / f"{caso}_salida.md").write_text(r["informe_md"], encoding="utf-8")
    print(f"{caso}: {r['estado']} · run {r['run_id']} · traza logs/{r['run_id']}.jsonl")
