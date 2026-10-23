"""La misma pregunta con y sin la capa de IO, lado a lado (Paso 12, JPTRS-65).

    python scripts/comparar_capa.py            # los tres ejemplos
    python scripts/comparar_capa.py caso3      # uno solo

Con la capa (SEMANTIC_LAYER=on): el esquema canónico de io-engine, sus definiciones y Meterless (H-MEM y World
Model). Sin la capa (SEMANTIC_LAYER=off): las tablas crudas tal como llegan de cada sistema, sin definiciones y
sin Meterless. Mismo modelo, misma pregunta, mismos datos.

En modo de muestra repite corridas reales grabadas: con capa, las de siempre; sin capa, las
<pregunta>-sincapa.json (se graban con SEMANTIC_LAYER=off python scripts/grabar_corridas.py). Deja las dos
trazas en logs/ y el lado a lado en ejemplos/comparacion_capa.md.
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


def una(pregunta, capa):
    os.environ["SEMANTIC_LAYER"] = "on" if capa else "off"
    os.environ["AGENTE_MEMORIA"] = tempfile.mkdtemp(prefix="hmem-")
    os.environ["AGENTE_MUNDO_DIR"] = tempfile.mkdtemp(prefix="mundo-")
    return correr(pregunta)


def celda(texto) -> str:
    return " ".join(str(texto or "—").split()).replace("|", "\\|")


def hipotesis(r) -> str:
    marca = {"sostenida": "✔", "descartada": "✘", "sin_decidir": "?"}
    return "<br>".join(f"{marca[h['veredicto']]} {celda(h['enunciado'])}" for h in r["hipotesis"]) or "—"


def cola(r) -> str:
    if not r["cola"]:
        return "—"
    return "<br>".join(f"{c['tipo']}{' ' + c['disputa_id'] if c['disputa_id'] else ''}: {c['estado']}" for c in r["cola"])


def fallidas(r) -> int:
    return sum(not e["ok"] for e in r["evidencia"])


casos = sys.argv[1:] or [p.name.removesuffix("_entrada.json") for p in sorted((RAIZ / "ejemplos").glob("*_entrada.json"))]
partes = ["# La misma pregunta, con y sin la capa de IO", "",
          "Mismo modelo, misma pregunta, mismos datos. **Con capa:** el esquema canónico de io-engine, sus definiciones "
          "y Meterless (H-MEM y World Model). **Sin capa** (`SEMANTIC_LAYER=off`): las tablas crudas tal como llegan "
          "de pagos, logística y soporte, sin definiciones ni Meterless. Las salidas salen de corridas reales "
          "(`python scripts/comparar_capa.py`), nunca escritas a mano.", ""]
for caso in casos:
    pregunta = json.loads((RAIZ / "ejemplos" / f"{caso}_entrada.json").read_text(encoding="utf-8"))["pregunta"]
    con, sin = una(pregunta, True), una(pregunta, False)
    filas = [
        ("Estado", con["estado"], sin["estado"]),
        ("Conclusión", con["conclusion"] or (con["abstencion"] or {}).get("razon"),
         sin["conclusion"] or (sin["abstencion"] or {}).get("razon")),
        ("Hipótesis", hipotesis(con), hipotesis(sin)),
        ("Qué conviene hacer", con["recomendacion"], sin["recomendacion"]),
        ("Consultas (fallidas)", f"{len(con['evidencia'])} ({fallidas(con)})", f"{len(sin['evidencia'])} ({fallidas(sin)})"),
        ("Vueltas · devoluciones", f"{con['metricas']['iteraciones']} · {con['metricas']['devoluciones']}",
         f"{sin['metricas']['iteraciones']} · {sin['metricas']['devoluciones']}"),
        ("Cola de aprobación", cola(con), cola(sin)),
        ("Traza", f"`logs/{con['run_id']}.jsonl`", f"`logs/{sin['run_id']}.jsonl`"),
    ]
    partes += [f"## {caso}", "", f"> {pregunta}", "", "| | Con la capa de IO | Sin la capa |", "| --- | --- | --- |"]
    partes += [f"| **{n}** | {a if n in ('Hipótesis', 'Cola de aprobación', 'Traza') else celda(a)} | "
               f"{b if n in ('Hipótesis', 'Cola de aprobación', 'Traza') else celda(b)} |" for n, a, b in filas]
    partes.append("")
    print(f"\n=== {caso}: {pregunta}")
    for etiqueta, r in (("con capa", con), ("sin capa", sin)):
        print(f"  {etiqueta}: {r['estado']} · {len(r['evidencia'])} consultas ({fallidas(r)} fallidas) · "
              f"{r['metricas']['iteraciones']} vueltas · traza logs/{r['run_id']}.jsonl")
        print("     →", (r["conclusion"] or (r["abstencion"] or {}).get("razon") or "")[:220])

salida = RAIZ / "ejemplos" / "comparacion_capa.md"
salida.write_text("\n".join(partes) + "\n", encoding="utf-8")
print(f"\nLado a lado en {salida.relative_to(RAIZ)}")
