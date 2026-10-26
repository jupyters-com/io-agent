"""El contrato del agente: cómo se ve una respuesta y cómo se ve un ítem de la cola de aprobación.

Los esquemas viven en contrato/*.schema.json (independientes del lenguaje). Aquí se validan,
junto con las reglas que un esquema no puede expresar:

1. "concluida" exige una conclusión y al menos una hipótesis SOSTENIDA con evidencia.
2. "abstencion" exige una razón y ninguna conclusión: el agente prefiere callar a inventar.
3. Toda hipótesis sostenida o descartada cita evidencia, y toda evidencia citada existe y
   vino de una consulta exitosa.
4. El informe Markdown tiene sus cuatro secciones.
"""

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

CARPETA = Path(__file__).resolve().parents[1] / "contrato"
SECCIONES_INFORME = ("## La pregunta", "## Lo que encontramos", "## Hipótesis descartadas",
                     "## Evidencia", "## Qué conviene hacer")


class ContratoRoto(ValueError):
    pass


@lru_cache
def esquema(nombre: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((CARPETA / f"{nombre}.schema.json").read_text(encoding="utf-8")))


def _errores_esquema(nombre: str, objeto: dict) -> list[str]:
    return [f"{'/'.join(map(str, e.path)) or '(raíz)'}: {e.message}" for e in esquema(nombre).iter_errors(objeto)]


def errores_respuesta(r: dict) -> list[str]:
    errores = _errores_esquema("respuesta", r)
    if errores:
        return errores
    evidencia = {e["id"]: e for e in r["evidencia"]}
    if r["estado"] == "concluida":
        if not r["conclusion"]:
            errores.append("concluida sin conclusión")
        if r["abstencion"] is not None:
            errores.append("concluida no puede traer abstención")
        if not any(h["veredicto"] == "sostenida" and h["evidencia"] for h in r["hipotesis"]):
            errores.append("concluida exige al menos una hipótesis sostenida con evidencia")
    else:
        if r["abstencion"] is None:
            errores.append("abstención sin razón")
        if r["conclusion"]:
            errores.append("abstención no puede traer conclusión")
    for h in r["hipotesis"]:
        if h["veredicto"] in ("sostenida", "descartada") and not h["evidencia"]:
            errores.append(f"{h['id']} está {h['veredicto']} sin evidencia")
        for ref in h["evidencia"]:
            if ref not in evidencia:
                errores.append(f"{h['id']} cita {ref}, que no existe")
            elif not evidencia[ref]["ok"]:
                errores.append(f"{h['id']} cita {ref}, que es una consulta fallida")
    for seccion in SECCIONES_INFORME:
        if seccion not in r["informe_md"]:
            errores.append(f"al informe le falta la sección '{seccion}'")
    return errores


def validar_respuesta(r: dict) -> dict:
    errores = errores_respuesta(r)
    if errores:
        raise ContratoRoto("; ".join(errores))
    return r


def validar_aprobacion(item: dict) -> dict:
    errores = _errores_esquema("aprobacion", item)
    if item.get("estado") != "pendiente" and not item.get("decidido_por"):
        errores.append("un ítem decidido debe decir quién lo decidió")
    if errores:
        raise ContratoRoto("; ".join(errores))
    return item


def validar_evento(evento: dict) -> dict:
    errores = _errores_esquema("traza", evento)
    if errores:
        raise ContratoRoto("; ".join(errores))
    return evento


# ---------------------------------------------------------------------------
# Informe legible para la dueña de la tienda (sobre esto se graba el video)
# ---------------------------------------------------------------------------
def _tabla(filas: list[dict], maximo=10) -> str:
    if not filas:
        return "_(sin filas)_"
    columnas = list(filas[0])
    lineas = ["| " + " | ".join(columnas) + " |", "| " + " | ".join("---" for _ in columnas) + " |"]
    for f in filas[:maximo]:
        lineas.append("| " + " | ".join(str(f.get(c, "")) for c in columnas) + " |")
    if len(filas) > maximo:
        lineas.append(f"\n_…y {len(filas) - maximo} filas más._")
    return "\n".join(lineas)


def informe(r: dict) -> str:
    """Arma el informe Markdown a partir de la respuesta (sin el campo informe_md)."""
    p = [f"# Informe de IO · {r['run_id']}", "", "## La pregunta", "", f"> {r['pregunta']}", "",
         "## Lo que encontramos", ""]
    if r["estado"] == "concluida":
        p.append(r["conclusion"])
        for h in (h for h in r["hipotesis"] if h["veredicto"] == "sostenida"):
            p.append(f"\n- **{h['enunciado']}** — {h['razon']} (evidencia: {', '.join(h['evidencia'])})")
    else:
        p.append(f"**IO no da una conclusión.** {r['abstencion']['razon']}")
    p += ["", "## Hipótesis descartadas", ""]
    descartadas = [h for h in r["hipotesis"] if h["veredicto"] == "descartada"]
    p += [f"- ~~{h['enunciado']}~~ — {h['razon']} (evidencia: {', '.join(h['evidencia'])})" for h in descartadas] \
        or ["_Ninguna en esta corrida._"]
    p += ["", "## Evidencia", ""]
    if r["evidencia"]:
        for e in r["evidencia"]:
            estado = f"motor: {e['motor']}" if e["ok"] else f"falló: {e.get('error')}"
            p += [f"**{e['id']}** · {estado}", "", "```sql", e["sql"].strip(), "```", "", _tabla(e["filas"]), ""]
    else:
        p.append("_No se consultaron datos._")
    p += ["", "## Qué conviene hacer", "", r["recomendacion"] or "_Sin recomendación: no hay conclusión._", "",
          "---", f"Aprobación: **{r['aprobacion']['estado']}** · modo {r['modo']} · "
          f"consultas: {r['metricas']['consultas']} · {r['metricas']['ms']:.0f} ms"]
    return "\n".join(p) + "\n"
