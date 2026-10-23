"""Evaluador (versión mínima): revisa lo que el Investigador quiere dar por final y lo devuelve
si falta evidencia. El Paso 10b (JPTRS-87) lo endurece; la regla de base ya rige:

- Toda hipótesis sostenida o descartada cita evidencia que existe, salió bien y trae filas.
- Para concluir hace falta al menos una hipótesis sostenida con evidencia.
- No se puede concluir con hipótesis sin veredicto, ni con menos de 2 hipótesis probadas.
- Si la recomendación dice qué hacer con disputas (pelear, resolver, reembolsar, aceptar), tiene que
  haber una consulta que cuente sus decisiones (`decision` / `razon_decision`): sin eso, el modelo
  inventa cuántas pelear.
- Las cantidades de la recomendación cuadran con esas decisiones: no se puede recomendar "pelear 14"
  si la evidencia dice que solo 4 tienen entrega confirmada y sin reclamo.
- La conclusión y la recomendación van en español simple: sin nombres de columnas ni "=true".
"""

import re

ACCIONES_SOBRE_DISPUTAS = re.compile(r"pele|resolver|reembols|aceptar", re.I)
CONSULTA_DE_DECISIONES = re.compile(r"\b(razon_)?decision\b", re.I)
# Qué razon_decision respalda cada acción recomendada.
ACCION_A_RAZONES = {
    "pelear": ("entrega_confirmada_sin_reclamo",),
    "resolver": ("reclamo_previo", "sin_prueba_de_entrega"),
    "reembolsar": ("sin_entrega",),
    "aceptar": ("sospecha_de_fraude",),
}
VERBO = re.compile(r"\b(pele\w*|resolver\w*|reembols\w*|acept\w*)", re.I)
NUMERO = re.compile(r"\b(\d{1,4})\b")
JERGA = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b|=\s*(?:true|false)\b"
                   r"|\b(?:fraudulent|unrecognized|highest|elevated)\b", re.I)  # también los valores en inglés
ID_DISPUTA = re.compile(r"^du_[A-Za-z0-9]+$")  # el id de una disputa no es jerga: la dueña lo ve en su panel
# Cualquier forma del verbo ("pelee", "peleó", "resolverlas", "acepte") lleva a su acción.
PREFIJO_A_ACCION = {"pele": "pelear", "reso": "resolver", "reem": "reembolsar", "acep": "aceptar"}


def jerga(texto: str) -> list[str]:
    """Nombres de columnas, valores en inglés o expresiones como "=true": lo que la dueña no entiende."""
    return sorted({m.group(0) for m in JERGA.finditer(texto or "") if not ID_DISPUTA.match(m.group(0))})


def revisar_hipotesis(hipotesis: list[dict]) -> list[str]:
    """Los enunciados también salen en el informe: en español simple."""
    problemas = []
    for h in hipotesis:
        palabras = jerga(str(h.get("enunciado", "")))
        if palabras:
            problemas.append(f"El enunciado de {h.get('id', 'una hipótesis')} lo lee la dueña de la tienda: "
                             f"reescríbelo sin términos técnicos ({', '.join(palabras[:6])}).")
    return problemas


def revisar_veredicto(veredicto: dict, evidencia: dict) -> list[str]:
    problemas = []
    if veredicto["veredicto"] in ("sostenida", "descartada"):
        if not veredicto["evidencia"]:
            problemas.append(f"{veredicto['hipotesis']} está {veredicto['veredicto']} sin citar evidencia.")
        for ref in veredicto["evidencia"]:
            e = evidencia.get(ref)
            if e is None:
                problemas.append(f"{veredicto['hipotesis']} cita {ref}, que no existe.")
            elif not e["ok"]:
                problemas.append(f"{veredicto['hipotesis']} cita {ref}, que es una consulta fallida.")
            elif e["n_filas"] == 0:
                problemas.append(f"{veredicto['hipotesis']} cita {ref}, que no devolvió filas.")
    if not veredicto.get("razon", "").strip():
        problemas.append(f"{veredicto['hipotesis']} no explica su veredicto.")
    palabras = jerga(veredicto.get("razon", ""))
    if palabras:
        problemas.append(f"La razón de {veredicto['hipotesis']} la lee la dueña de la tienda: reescríbela sin "
                         f"términos técnicos ({', '.join(palabras[:6])}). Ejemplo: 'producto no recibido' en vez "
                         "de product_not_received.")
    return problemas


def _totales_por_razon(evidencia: dict) -> tuple[dict, str]:
    """Total de disputas por razon_decision según las consultas de decisiones (la de mayor total)."""
    mejor, cual = {}, ""
    for e in evidencia.values():
        if not (e["ok"] and e["filas"] and "razon_decision" in e["filas"][0]):
            continue
        totales = {}
        for f in e["filas"]:
            numeros = {k: v for k, v in f.items() if isinstance(v, (int, float)) or str(v).isdigit()}
            if not numeros:
                continue
            clave = next((k for k in numeros if re.fullmatch(r"(cnt|count|n|total|disputas|cantidad)\w*", k, re.I)),
                         next(iter(numeros)))
            totales[f["razon_decision"]] = totales.get(f["razon_decision"], 0) + int(float(numeros[clave]))
        if sum(totales.values()) > sum(mejor.values()):
            mejor, cual = totales, e["id"]
    return mejor, cual


def _cantidades_fuera_de_la_evidencia(recomendacion: str, evidencia: dict) -> list[str]:
    totales, cual = _totales_por_razon(evidencia)
    if not totales:
        return []
    problemas = []
    for m in VERBO.finditer(recomendacion):
        verbo = m.group(1).lower()
        accion = PREFIJO_A_ACCION.get(verbo[:4])
        if accion is None:
            continue
        tramo = recomendacion[m.end(): m.end() + 60]
        n = next((int(x) for x in NUMERO.findall(tramo) if int(x) < 1900), None)
        if n is None:
            continue
        maximo = sum(totales.get(r, 0) for r in ACCION_A_RAZONES[accion])
        if n > maximo:
            problemas.append(f'La recomendación dice "{m.group(1)} … {n}", pero según {cual} solo hay {maximo} '
                             f"disputa(s) con razón {' o '.join(ACCION_A_RAZONES[accion])}. Usa los números de {cual}.")
    return problemas


def revisar_conclusion(hipotesis: dict, evidencia: dict, conclusion: str = "", recomendacion: str = "",
                       capa: bool = True) -> list[str]:
    """capa=False (SEMANTIC_LAYER=off): las reglas que usan definiciones de la capa de IO (contar decisiones con
    razon_decision y cuadrar las cantidades con ellas) no aplican, porque en las tablas crudas no existen. Las
    demás (evidencia real, comparar hipótesis, español simple) son del Evaluador y siguen igual."""
    problemas = []
    decididas = [h for h in hipotesis.values() if h["veredicto"] in ("sostenida", "descartada")]
    if len(decididas) < 2:
        problemas.append("Explicar por qué exige comparar: prueba al menos 2 hipótesis distintas (incluida la "
                         "explicación contraria a tu conclusión) y dales veredicto antes de concluir.")
    if capa and recomendacion and ACCIONES_SOBRE_DISPUTAS.search(recomendacion):
        if not any(e["ok"] and e["n_filas"] and CONSULTA_DE_DECISIONES.search(e["sql"]) for e in evidencia.values()):
            problemas.append("La recomendación dice qué hacer con las disputas, pero ninguna consulta contó sus "
                             "decisiones. Consulta cuántas disputas del grupo hay por razon_decision y usa esos "
                             "números en la recomendación.")
    if capa:
        problemas += _cantidades_fuera_de_la_evidencia(recomendacion or "", evidencia)
    palabras = jerga(f"{conclusion} {recomendacion}")
    if palabras:
        problemas.append(f"La conclusión y la recomendación son para la dueña de la tienda: reescríbelas sin "
                         f"términos técnicos ({', '.join(palabras[:6])}). Ejemplo: 'producto no recibido' en vez "
                         f"de product_not_received.")
    sin_veredicto = [h["id"] for h in hipotesis.values() if h["veredicto"] == "sin_decidir"]
    if sin_veredicto:
        problemas.append(f"Hay hipótesis sin veredicto: {', '.join(sin_veredicto)}. Pruébalas o descártalas.")
    if not any(h["veredicto"] == "sostenida" and h["evidencia"] for h in hipotesis.values()):
        problemas.append("Para concluir hace falta al menos una hipótesis sostenida con evidencia.")
    for h in hipotesis.values():
        if h["veredicto"] != "sin_decidir":
            problemas += revisar_veredicto({"hipotesis": h["id"], **h}, evidencia)
    return problemas
