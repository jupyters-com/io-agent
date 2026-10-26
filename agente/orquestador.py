"""El orquestador: recibe una pregunta y devuelve una respuesta que cumple el contrato.

1. El Investigador (agente/investigador.py) propone hipótesis, las prueba con consultar(sql) y
   descarta las que la evidencia no sostiene. El Evaluador revisa cada veredicto y la conclusión.
2. La respuesta pasa por la cola de aprobación.
3. Todo queda en logs/: la traza (<run_id>.jsonl), las filas de evidencia (<run_id>.evidencia.jsonl)
   y la cola (cola_aprobacion.jsonl). La respuesta y el informe van a salidas/.

Modo de muestra: repite una corrida real grabada para esa pregunta (samples/corridas/). Con
AGENTE_GRABAR=true en modo real, la corrida se graba para que el modo de muestra la repita.
"""

import hashlib
import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agente import cola as cola_mod
from agente import config as config_mod
from agente import contrato, datos, modelo
from agente.investigador import Investigador
from agente.memoria import Memoria
from agente.mundo import MundoAgente
from agente.preparador import Preparador
from agente.traza import Cronometro, Traza

PANORAMA = """
SELECT motivo, count(*) AS disputas, sum(CASE WHEN decision = 'pelear' THEN 1 ELSE 0 END) AS vale_pelear
FROM canonico.disputas
GROUP BY motivo
ORDER BY disputas DESC, motivo
"""


def nuevo_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _norm_pregunta(p: str) -> str:
    return " ".join(p.lower().split())


def nombre_corrida(pregunta: str) -> str:
    base = unicodedata.normalize("NFKD", pregunta).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:50]
    return f"{base}-{hashlib.sha1(_norm_pregunta(pregunta).encode()).hexdigest()[:6]}"


def corrida_grabada(cfg, pregunta: str, con_memoria: bool = False) -> dict | None:
    """La corrida grabada para esa pregunta. Con memoria, prefiere la que se grabó con H-MEM encendido
    (<nombre>-hmem.json); si no hay, usa la otra. Con SEMANTIC_LAYER=off, solo las grabadas sin la capa
    (<nombre>-sincapa.json), y al revés: nunca se mezclan."""
    carpeta = Path(cfg.muestras).parent / "corridas"
    capa = getattr(cfg, "capa_semantica", True)
    encontradas = {}
    for ruta in sorted(carpeta.glob("*.json")) if carpeta.exists() else []:
        c = json.loads(ruta.read_text(encoding="utf-8"))
        if _norm_pregunta(c["pregunta"]) == _norm_pregunta(pregunta) and c.get("capa", "on") == ("on" if capa else "off"):
            encontradas[bool(c.get("con_memoria"))] = c
    return encontradas.get(con_memoria) or encontradas.get(not con_memoria)


def _consultar(fuente, sql, traza, cfg, etiqueta=""):
    """Una llamada a consultar(sql) con un reintento si se pasa del tiempo."""
    reintentos = 0
    while True:
        with Cronometro() as t:
            try:
                r = fuente.consultar(sql)
                error = None
            except (TimeoutError, ConnectionError) as e:
                r, error = {"ok": False, "motor": None, "filas": [], "n_filas": 0, "error": str(e)}, e
        if isinstance(error, TimeoutError) and reintentos < 1:
            reintentos += 1
            continue
        entrada = f"{etiqueta} · {sql}" if etiqueta else sql
        traza.evento("investigador", "io-engine.consultar", "consultar", entrada=entrada,
                     salida=(f"{r.get('n_filas', 0)} filas · motor={r.get('motor')}" if r.get("ok")
                             else f"error: {r.get('error')}"),
                     estado="ok" if r.get("ok") else "error", reintentos=reintentos, ms=t.ms)
        return r


def correr(pregunta: str, cfg=None, run_id: str | None = None) -> dict:
    cfg = cfg or config_mod.cargar()
    run_id = run_id or nuevo_run_id()
    traza = Traza(run_id, cfg.logs)
    grabar = not cfg.modo_muestra and os.getenv("AGENTE_GRABAR", "").lower() in ("1", "true", "si", "sí")

    # H-MEM (Meterless): antes de empezar, lo que IO aprendió en corridas anteriores
    memoria = Memoria(cfg, traza, nombre_corrida(pregunta))
    contexto = memoria.recordar(pregunta)

    grabada = corrida_grabada(cfg, pregunta, con_memoria=bool(contexto)) if cfg.modo_muestra else None
    fuente = datos.crear(cfg, extra=(grabada or {}).get("consultas"))
    if not cfg.capa_semantica:  # sin la capa, canonico/mapeo/origen no existen para el agente
        fuente = datos.SoloCrudo(fuente)
    llm = modelo.crear(cfg, turnos=(grabada or {}).get("turnos"))
    if grabar:
        fuente, llm = datos.FuenteGrabadora(fuente), modelo.Grabadora(llm)

    ruta_evidencia = Path(cfg.logs) / f"{run_id}.evidencia.jsonl"
    mundo = MundoAgente(cfg, traza, run_id)  # World Model (Meterless): las cosas que se vieron y de dónde

    def registrar_evidencia(e, hipotesis):
        with open(ruta_evidencia, "a", encoding="utf-8") as f:
            f.write(json.dumps({"run_id": run_id, "hipotesis": hipotesis, **e}, ensure_ascii=False, default=str) + "\n")
        mundo.ingerir(e)

    with Cronometro() as total:
        traza.evento("orquestador", "agente", "recibir_pregunta", entrada=pregunta,
                     salida=f"modo={cfg.modo} capa={'on' if cfg.capa_semantica else 'off'} fuente={fuente.nombre} "
                            f"modelo={llm.nombre}"
                            + (f" corrida={grabada['nombre']}" if grabada else ""))
        memoria.publicar()
        mundo.abrir_corrida(pregunta)

        investigador = Investigador(cfg, fuente, llm, traza, _consultar, registrar_evidencia, mundo=mundo)
        resultado = investigador.investigar(pregunta, memoria=contexto)
        memoria.aprender(pregunta, run_id, resultado, investigador.motivos_devueltos)

        # Paso 11: separar las disputas, redactar las respuestas al banco y dejarlas en la cola (no se envía nada)
        def consultar_evidencia(sql):
            r = _consultar(fuente, sql, traza, cfg, etiqueta="preparación")
            e = {"id": f"E{len(resultado['evidencia']) + 1}", "sql": " ".join(sql.split()), "motor": r.get("motor"),
                 "ok": bool(r.get("ok")), "filas": r.get("filas", []), "n_filas": int(r.get("n_filas", 0)),
                 "error": r.get("error")}
            resultado["evidencia"].append(e)
            registrar_evidencia(e, "preparacion")
            return e
        if cfg.capa_semantica:
            entradas = Preparador(consultar_evidencia, traza).preparar(pregunta, resultado, mundo.anclas,
                                                                       cfg.mundo_activo)
        else:  # la cola usa las definiciones de la capa (vale_pelear, razon_decision): sin capa no hay con qué
            entradas = []
            traza.evento("cola", "agente", "preparar", estado="omitido",
                         salida="SEMANTIC_LAYER=off: sin la capa de IO no hay con qué separar ni redactar respuestas")

        if llm.costo_usd > cfg.presupuesto_usd:
            traza.evento("orquestador", "modelo", "alerta_gasto",
                         salida=f"gasto {llm.costo_usd:.4f} USD > presupuesto {cfg.presupuesto_usd} USD",
                         estado="alerta")

        respuesta = {
            "version": "0.1", "run_id": run_id, "pregunta": pregunta, "modo": cfg.modo,
            "estado": resultado["estado"], "conclusion": resultado["conclusion"],
            "hipotesis": resultado["hipotesis"], "evidencia": resultado["evidencia"],
            "recomendacion": resultado["recomendacion"], "abstencion": resultado["abstencion"],
            "aprobacion": {"item_id": "", "estado": "pendiente"}, "cola": [],
            "metricas": {"iteraciones": resultado["iteraciones"], "consultas": len(resultado["evidencia"]),
                         "ms": 0.0, "tokens": llm.tokens, "costo_usd": round(llm.costo_usd, 6),
                         "devoluciones": investigador.n_devoluciones, "memorias_usadas": len(memoria.usadas),
                         "entidades_ancladas": mundo.verificadas,
                         "capa_semantica": "on" if cfg.capa_semantica else "off"},
            "informe_md": "",
        }

        cola = cola_mod.ColaAprobacion(cfg.logs)
        conclusion = {"tipo": "conclusion", "estado_corrida": resultado["estado"],
                      "resumen": respuesta["conclusion"] or respuesta["abstencion"]["razon"],
                      "evidencia": sorted({ref for h in resultado["hipotesis"] for ref in h["evidencia"]})}
        for n, entrada in enumerate([conclusion, *entradas]):
            item = contrato.validar_aprobacion(cola.encolar(run_id, entrada, n))
            traza.evento("cola", "cola_aprobacion", "encolar",
                         entrada=f"{item['tipo']}" + (f" {item['disputa_id']}" if item["disputa_id"] else "")
                                 + f" · {item['resumen']}",
                         salida=f"{item['item_id']} · {item['estado']} por {item['decidido_por']} · {item['motivo']}",
                         estado="ok" if item["estado"] == "aprobada" else "alerta")
            resumen = {k: item[k] for k in ("item_id", "tipo", "disputa_id", "estado", "motivo", "borrador")}
            if n == 0:
                respuesta["aprobacion"] = {"item_id": item["item_id"], "estado": item["estado"]}
            else:
                respuesta["cola"].append(resumen)
        respuesta["metricas"]["consultas"] = len(resultado["evidencia"])

    respuesta["metricas"]["ms"] = round(total.ms, 1)
    respuesta["informe_md"] = contrato.informe(respuesta)
    contrato.validar_respuesta(respuesta)

    cfg.salidas.mkdir(parents=True, exist_ok=True)
    (cfg.salidas / f"{run_id}.json").write_text(json.dumps(respuesta, ensure_ascii=False, indent=2, default=str),
                                                encoding="utf-8")
    (cfg.salidas / f"{run_id}.md").write_text(respuesta["informe_md"], encoding="utf-8")
    traza.evento("orquestador", "salida", "entregar", entrada=respuesta["estado"],
                 salida=f"salidas/{run_id}.json + .md")

    if grabar:
        motivo = _por_que_no_grabar(cfg, pregunta, resultado, bool(contexto))
        if motivo:
            traza.evento("orquestador", "salida", "grabar_corrida", estado="omitido", salida=f"no se graba: {motivo}")
        else:
            archivo = _guardar_corrida(cfg, pregunta, run_id, fuente, llm, resultado["estado"], contexto)
            traza.evento("orquestador", "salida", "grabar_corrida", salida=f"samples/corridas/{archivo}")
    return respuesta


def _por_que_no_grabar(cfg, pregunta, resultado, con_memoria=False) -> str | None:
    """Una corrida se graba salvo que el modelo no haya respondido, o que vaya a pisar una corrida
    concluida con una abstención (una buena grabación no se pierde por un mal intento)."""
    if resultado["fallo_modelo"]:
        return "el modelo no respondió, la corrida no sirve para el modo de muestra"
    anterior = corrida_grabada(cfg.__class__(**{**cfg.__dict__, "modo_muestra": True}), pregunta, con_memoria)
    if anterior and bool(anterior.get("con_memoria")) != con_memoria:
        anterior = None  # la otra variante no cuenta: no se pisan entre sí
    if anterior and anterior.get("estado") == "concluida" and resultado["estado"] != "concluida":
        return "ya hay una corrida concluida grabada para esta pregunta y esta se abstuvo"
    return None


def _guardar_corrida(cfg, pregunta, run_id, fuente, llm, estado, contexto=""):
    nombre = nombre_corrida(pregunta) + ("-hmem" if contexto else "") + ("" if cfg.capa_semantica else "-sincapa")
    carpeta = Path(cfg.muestras).parent / "corridas"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{nombre}.json").write_text(json.dumps({
        "_synthetic": True,
        "nombre": nombre,
        "pregunta": pregunta,
        "origen": f"corrida real {run_id}: modelo {cfg.meterless_modelo} vía Nightshift, datos de io-engine",
        "grabado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "estado": estado,
        "con_memoria": bool(contexto),
        "capa": "on" if cfg.capa_semantica else "off",
        "memoria": contexto,
        "turnos": llm.turnos,
        "consultas": fuente.consultas,
    }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return f"{nombre}.json"
