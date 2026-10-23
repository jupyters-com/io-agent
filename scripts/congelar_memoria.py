"""Copia la memoria real (memoria/) y el World Model real (mundo/) a samples/, lo que usa el modo de muestra.

    python scripts/congelar_memoria.py

Hazlo después de grabar las corridas. samples/memoria/ y samples/mundo/ sí se suben al repo: solo tienen
lo que el agente aprendió y vio en los datos sintéticos (sin claves ni datos reales); revísalos antes.
"""

import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
copias = {"memoria": ("memorias.json", "ledger.jsonl"), "mundo": ("eventos.jsonl",)}
for carpeta, archivos in copias.items():
    origen, destino = RAIZ / carpeta, RAIZ / "samples" / carpeta
    if not (origen / archivos[0]).exists():
        print(f"No hay {carpeta}/{archivos[0]}: corre antes scripts/grabar_corridas.py. Se omite.")
        continue
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in archivos:
        shutil.copyfile(origen / nombre, destino / nombre)
    if carpeta == "memoria":
        n = len(json.loads((destino / "memorias.json").read_text(encoding="utf-8"))["records"])
        print(f"samples/memoria/ actualizado: {n} memorias + su libro de confianza.")
    else:
        n = sum(1 for l in (destino / "eventos.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())
        print(f"samples/mundo/ actualizado: {n} eventos del World Model.")
