"""Graba en samples/consultas.json las consultas que el agente arma SOLO (la cola de aprobación, Paso 11).

    # 1. en io-engine:      docker compose up --build
    # 2. en este repo:      python scripts/completar_muestras.py

Repite los tres ejemplos en modo de muestra, con y sin Meterless, a partir de las corridas grabadas (no
llama al modelo). Cuando el agente pide algo que no está grabado (las disputas del grupo, los mensajes de
soporte), se lo pregunta a io-engine y lo guarda tal cual. Después el modo de muestra ya no necesita el motor.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)
os.environ.update(SAMPLE_MODE="true", AGENTE_COMPLETAR_MUESTRAS="true", AGENTE_GRABAR="")

from agente import datos  # noqa: E402
from agente.orquestador import correr  # noqa: E402

creadas = []
original = datos.crear


def crear(cfg, extra=None):
    f = original(cfg, extra)
    creadas.append(f)
    return f


datos.crear = crear
for entrada in sorted((RAIZ / "ejemplos").glob("*_entrada.json")):
    caso = entrada.name.removesuffix("_entrada.json")
    pregunta = json.loads(entrada.read_text(encoding="utf-8"))["pregunta"]
    for con in (False, True):
        os.environ["AGENTE_HMEM"] = os.environ["AGENTE_MUNDO"] = "true" if con else "false"
        os.environ["AGENTE_MEMORIA"] = tempfile.mkdtemp(prefix="hmem-")
        os.environ["AGENTE_MUNDO_DIR"] = tempfile.mkdtemp(prefix="mundo-")
        r = correr(pregunta)
        nuevas = getattr(creadas[-1], "nuevas", [])
        cola = ", ".join(f"{c['tipo']}{' ' + c['disputa_id'] if c['disputa_id'] else ''}={c['estado']}" for c in r["cola"])
        print(f"{caso} {'con' if con else 'sin'} Meterless: {r['estado']} · {len(nuevas)} consulta(s) nueva(s) grabada(s)"
              f" · cola: {cola or '-'}")
print("\nListo: samples/consultas.json tiene lo que la cola necesita.")
