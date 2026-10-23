"""Mide el agente con y sin la capa de IO sobre el set de prueba ([Challenge] JPTRS-78).

    # io-engine (docker compose up) y Nightshift abiertos
    python scripts/medir_set.py --primeros 5     # la prueba corta de mitad de semana
    python scripts/medir_set.py                  # el set completo (se puede cortar con Ctrl+C y retomar)
    python scripts/medir_set.py --tabla          # solo rehace la tabla con lo ya medido

A cada disputa del set le pregunta "¿Vale la pena pelear la disputa …?" en modo real, con la capa encendida y
apagada (SEMANTIC_LAYER), una detrás de la otra. Cada respuesta queda en evaluacion/resultados/<con|sin>/ y su
traza en evaluacion/logs/<con|sin>/. Lo ya medido no se repite; una corrida en la que Nightshift no respondió
sí se repite la próxima vez. Al final deja la tabla lado a lado en evaluacion/medicion.md.

Para que una corrida no contamine a otra: cada modo es una app distinta en Nightshift, y la memoria (H-MEM) y
el World Model de la medición viven aparte (evaluacion/_memoria, evaluacion/_mundo), arrancando de samples/.
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from agente import medicion  # noqa: E402

EVAL = RAIZ / "evaluacion"
MODOS = {"con": "on", "sin": "off"}


def ruta_resultado(modo, disputa):
    return EVAL / "resultados" / modo / f"{disputa}.json"


def leer(modo, disputa):
    ruta = ruta_resultado(modo, disputa)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def fallo_del_proveedor(r) -> bool:
    razon = str((r.get("abstencion") or {}).get("razon") or "")
    return r["estado"] == "abstencion" and ("No pude hablar con el modelo" in razon or "respondió 3 veces" in razon)


def preparar_entorno():
    for carpeta, semilla in (("_memoria", "memoria"), ("_mundo", "mundo")):
        destino = EVAL / carpeta
        if not destino.exists() and (RAIZ / "samples" / semilla).exists():
            shutil.copytree(RAIZ / "samples" / semilla, destino)
        destino.mkdir(parents=True, exist_ok=True)
    os.environ.update(SAMPLE_MODE="false", AGENTE_GRABAR="", AGENTE_MEMORIA=str(EVAL / "_memoria"),
                      AGENTE_MUNDO_DIR=str(EVAL / "_mundo"))


def medir(caso, modo):
    from agente.orquestador import correr
    os.environ["SEMANTIC_LAYER"] = MODOS[modo]
    os.environ["METERLESS_APP"] = "io-agent-medicion" if modo == "con" else "io-agent-medicion-sin-capa"
    os.environ["AGENTE_LOGS"] = str(EVAL / "logs" / modo)
    inicio = time.time()
    r = correr(f"¿Vale la pena pelear la disputa {caso['disputa_id']}?")
    ruta = ruta_resultado(modo, caso["disputa_id"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    p = medicion.puntuar(caso, r)
    print(f"  {modo} capa: {p['resultado']:<30} dijo {p['dijo']:<12} · {time.time() - inicio:.0f} s · "
          f"{(r['conclusion'] or (r['abstencion'] or {}).get('razon') or '')[:110]}")


def tabla(casos):
    filas = {m: [medicion.puntuar(c, leer(m, c["disputa_id"])) for c in casos] for m in MODOS}
    res = {m: medicion.resumen(filas[m]) for m in MODOS}
    lineas = ["# Medición: el agente con y sin la capa de IO sobre el set de prueba", "",
              f"Set: `evaluacion/set_prueba.csv` ({len(casos)} disputas con su respuesta esperada, según la definición "
              "del esquema canónico). A cada una se le preguntó al agente \"¿Vale la pena pelear la disputa …?\" con "
              "la capa encendida y apagada (`SEMANTIC_LAYER`), en modo real: mismo modelo, mismos datos. Generado con "
              "`python scripts/medir_set.py`; las respuestas están en `evaluacion/resultados/` y las trazas en "
              "`evaluacion/logs/`.", "",
              "| | Con la capa de IO | Sin la capa |", "| --- | --- | --- |"]
    for clave, nombre in (("medidos", "Disputas medidas"), ("acierto", "Aciertos (decisión y razón correctas)"),
                          ("tasa_acierto", "% de acierto"),
                          ("acierto con una razón falsa", "Decisión correcta por una razón falsa (\"no hubo entrega\" "
                                                          "cuando sí la hubo)"),
                          ("tasa_decision", "% de decisión correcta, sin mirar la razón"),
                          ("defensa que no debía armarse", "Defensas que no debían armarse"),
                          ("defensa perdida", "Defensas perdidas (convenía pelear y dijo que no)"),
                          ("abstención", "Abstenciones"), ("sin clasificar", "Sin clasificar")):
        a, b = res["con"][clave], res["sin"][clave]
        sufijo = " %" if clave.startswith("tasa") else ""
        lineas.append(f"| **{nombre}** | {a}{sufijo} | {b}{sufijo} |")
    for modo, nombre in (("con", "con la capa"), ("sin", "sin la capa")):
        perdidas = [c for c, f in zip(casos, filas[modo]) if f["resultado"] == "defensa perdida"]
        if perdidas:
            total = sum(float(c["monto"] or 0) for c in perdidas)
            abiertas = [c for c in perdidas if c["estado"] == "needs_response"]
            lineas += ["", f"**Defensas perdidas {nombre}:** {len(perdidas)} disputas que convenía pelear, por "
                           f"{total:,.2f} USD en total; {len(abiertas)} siguen esperando respuesta "
                           f"({sum(float(c['monto'] or 0) for c in abiertas):,.2f} USD)."]
    lineas += ["", "## Disputa por disputa", "",
               "| disputa | esperada | con la capa | sin la capa |", "| --- | --- | --- | --- |"]
    for c, a, b in zip(casos, filas["con"], filas["sin"]):
        lineas.append(f"| {c['disputa_id']} | {c['esperada']} | {a['resultado']} | {b['resultado']} |")
    abst = [(m, c["disputa_id"], f) for m in MODOS for c, f in zip(casos, filas[m]) if f["resultado"] == "abstención"]
    if abst:
        lineas += ["", "## Abstenciones y su razón", ""]
        lineas += [f"- **{d}** ({m} la capa): {f['detalle']}" for m, d, f in abst]
    (EVAL / "medicion.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--primeros", type=int, default=0, help="medir solo las primeras N disputas del set")
    ap.add_argument("--tabla", action="store_true", help="no correr nada: rehacer la tabla con lo ya medido")
    args = ap.parse_args()
    casos = medicion.leer_set(EVAL / "set_prueba.csv")
    if args.primeros:
        # para la prueba corta: casos variados, no los primeros por orden alfabético
        por_tipo = {}
        for c in casos:
            por_tipo.setdefault(c["razon_decision"], []).append(c)
        mezcla = [c for grupo in zip(*por_tipo.values()) for c in grupo] + casos
        casos = list({c["disputa_id"]: c for c in mezcla}.values())[:args.primeros]
    if not args.tabla:
        preparar_entorno()
        for i, caso in enumerate(casos, 1):
            print(f"\n[{i}/{len(casos)}] {caso['disputa_id']} · esperada: {caso['esperada']}")
            for modo in MODOS:
                previa = leer(modo, caso["disputa_id"])
                if previa and not fallo_del_proveedor(previa):
                    print(f"  {modo} capa: ya medida ({medicion.puntuar(caso, previa)['resultado']})")
                    continue
                medir(caso, modo)
    res = tabla(casos)
    print("\n                         con capa   sin capa")
    for clave in ("medidos", "acierto", "acierto con una razón falsa", "defensa que no debía armarse",
                  "defensa perdida", "abstención", "sin clasificar"):
        print(f"  {clave:<30} {res['con'][clave]:>6}   {res['sin'][clave]:>6}")
    print(f"  {'% de acierto':<30} {res['con']['tasa_acierto']:>6}   {res['sin']['tasa_acierto']:>6}")
    print(f"  {'% decisión (sin mirar razón)':<30} {res['con']['tasa_decision']:>6}   {res['sin']['tasa_decision']:>6}")
    print("\nTabla en evaluacion/medicion.md")


if __name__ == "__main__":
    main()
