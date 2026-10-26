"""¿Qué cambia si se apaga Meterless (H-MEM y World Model)? Corre los tres ejemplos con y sin, y compara.

    python scripts/comparar_memoria.py

En modo de muestra repite corridas reales grabadas: sin Meterless, las normales; con Meterless, las
<pregunta>-hmem.json (grabadas con H-MEM y World Model encendidos). Cada corrida arranca de una copia
limpia de samples/memoria/ y samples/mundo/, así el resultado no depende del orden. Las trazas quedan
en logs/: con Meterless se ven los eventos recordar/aprender (memoria) y abrir_corrida/ingerir/anclar
(mundo); sin Meterless, esos mismos eventos como "omitido".
"""

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)
os.environ.setdefault("SAMPLE_MODE", "true")
os.environ["AGENTE_GRABAR"] = ""

from agente.orquestador import correr  # noqa: E402


def una(pregunta, con_memoria):
    os.environ["AGENTE_HMEM"] = os.environ["AGENTE_MUNDO"] = "true" if con_memoria else "false"
    os.environ["AGENTE_MEMORIA"] = tempfile.mkdtemp(prefix="hmem-")
    os.environ["AGENTE_MUNDO_DIR"] = tempfile.mkdtemp(prefix="mundo-")
    r = correr(pregunta)
    traza = [json.loads(l) for l in (RAIZ / "logs" / f"{r['run_id']}.jsonl").read_text(encoding="utf-8").splitlines()]
    corrida = next((e["salida"].split("corrida=")[-1] for e in traza
                    if e["accion"] == "recibir_pregunta" and "corrida=" in e["salida"]), "en vivo")
    return r, corrida


filas = []
for entrada in sorted((RAIZ / "ejemplos").glob("*_entrada.json")):
    caso = entrada.name.removesuffix("_entrada.json")
    pregunta = json.loads(entrada.read_text(encoding="utf-8"))["pregunta"]
    for con in (False, True):
        r, corrida = una(pregunta, con)
        m = r["metricas"]
        filas.append((caso, "con Meterless" if con else "sin Meterless", r["estado"], m["iteraciones"],
                      m["devoluciones"], m["consultas"], m["memorias_usadas"], m["entidades_ancladas"],
                      f"logs/{r['run_id']}.jsonl", corrida))

titulos = ("caso", "meterless", "estado", "vueltas", "devoluciones", "consultas", "memorias", "ancladas", "traza",
           "corrida")
anchos = [max(len(str(x)) for x in col) for col in zip(titulos, *filas)]
for fila in (titulos, *filas):
    print("  ".join(str(x).ljust(a) for x, a in zip(fila, anchos)))
