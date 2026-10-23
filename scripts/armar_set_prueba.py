"""Arma el set de prueba ([Challenge] JPTRS-77): cada disputa de los datos sintéticos con su respuesta esperada.

    # 1. en io-engine:      docker compose up
    # 2. en este repo:      python scripts/armar_set_prueba.py

La respuesta esperada sale de la definición del esquema canónico de io-engine (paso 7), no de las reglas de
las redes de tarjetas:
- "vale la pena pelear":  vale_pelear (entrega confirmada con prueba, sin reclamo previo, menos de 2 señales).
- "causa operativa":      no vale pelear y la entrega falló en una zona con atrasos del transportista.
- "no vale la pena":      el resto (reclamo previo, sin prueba de entrega, sospecha de fraude).
La columna caso_limite marca dónde el agente sin la capa puede equivocarse y por qué.
Deja evaluacion/set_prueba.csv y evaluacion/set_prueba.md.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from agente import config, medicion  # noqa: E402
from agente.datos import FuenteMotor  # noqa: E402

SQL = ("SELECT disputa_id, motivo, estado, monto, transportista, region, entrega_confirmada, vale_pelear, "
       "razon_decision, causa_operativa "
       "FROM canonico.disputas ORDER BY disputa_id")

cfg = config.cargar()
r = FuenteMotor(cfg.motor_url, max(cfg.timeout_s, 90)).consultar(SQL)
if not r.get("ok"):
    sys.exit(f"io-engine respondió con error: {r.get('error')}")
filas = medicion.filas_del_set(r["filas"])
medicion.escribir_set(RAIZ / "evaluacion" / "set_prueba.csv", filas)

cuenta = {e: sum(f["esperada"] == e for f in filas) for e in medicion.ESPERADAS}
lineas = ["# Set de prueba · disputas con su respuesta esperada", "",
          f"{len(filas)} disputas de los datos sintéticos (todas las que hay). La respuesta esperada sale de la "
          "definición del esquema canónico de io-engine (`vale_pelear`, `razon_decision`, `causa_operativa`), "
          "no de reglas de las redes de tarjetas. Generado con `python scripts/armar_set_prueba.py`.", "",
          " · ".join(f"**{e}**: {n}" for e, n in cuenta.items()), "",
          "| disputa | respuesta esperada | razón | caso límite (dónde se equivocaría sin la capa) |",
          "| --- | --- | --- | --- |"]
lineas += [f"| {f['disputa_id']} | {f['esperada']} | {f['razon']} | {f['caso_limite'] or '—'} |" for f in filas]
(RAIZ / "evaluacion" / "set_prueba.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
print(f"{len(filas)} disputas · " + " · ".join(f"{e}: {n}" for e, n in cuenta.items()))
print("Set en evaluacion/set_prueba.csv y evaluacion/set_prueba.md")
