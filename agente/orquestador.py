"""El esqueleto del agente: recibe una pregunta y devuelve una respuesta que cumple el contrato.

Todavía no investiga (eso es el Paso 10, JPTRS-67). Hoy hace el recorrido completo con un
plan mínimo: mira el panorama de las disputas con consultar(sql) y, como no tiene con qué
probar hipótesis, se ABSTIENE en vez de inventar. Cada paso queda en la traza JSONL y la
respuesta pasa por la cola de aprobación.

Topes: AGENTE_TIMEOUT_S por llamada externa (con un reintento), AGENTE_MAX_ITERACIONES por
corrida y AGENTE_PRESUPUESTO_USD como alerta de gasto en el proveedor del modelo.
"""

import json
import uuid
from datetime import datetime, timezone

from agente import cola as cola_mod
from agente import config as config_mod
from agente import contrato, datos, modelo
from agente.traza import Cronometro, Traza

PANORAMA = """
SELECT motivo, count(*) AS disputas, sum(CASE WHEN decision = 'pelear' THEN 1 ELSE 0 END) AS vale_pelear
FROM canonico.disputas
GROUP BY motivo
ORDER BY disputas DESC, motivo
"""

RAZON_ESQUELETO = ("El investigador todavía no está implementado (Paso 10): IO puede ver el panorama de "
                   "las disputas, pero aún no prueba hipótesis, así que prefiere no concluir.")


def nuevo_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _consultar(fuente, sql, traza, cfg):
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
        traza.evento("investigador", "io-engine.consultar", "consultar", entrada=sql,
                     salida=(f"{r.get('n_filas', 0)} filas · motor={r.get('motor')}" if r.get("ok")
                             else f"error: {r.get('error')}"),
                     estado="ok" if r.get("ok") else "error", reintentos=reintentos, ms=t.ms)
        return r


def correr(pregunta: str, cfg=None, run_id: str | None = None) -> dict:
    cfg = cfg or config_mod.cargar()
    run_id = run_id or nuevo_run_id()
    traza = Traza(run_id, cfg.logs)
    fuente, llm = datos.crear(cfg), modelo.crear(cfg)

    with Cronometro() as total:
        traza.evento("orquestador", "agente", "recibir_pregunta", entrada=pregunta,
                     salida=f"modo={cfg.modo} fuente={fuente.nombre} modelo={llm.nombre}")

        plan = [("panorama", PANORAMA)]
        evidencia, iteraciones = [], 0
        for nombre, sql in plan:
            if iteraciones >= cfg.max_iteraciones:
                traza.evento("orquestador", "agente", "tope_iteraciones", entrada=nombre,
                             salida=f"se alcanzó AGENTE_MAX_ITERACIONES={cfg.max_iteraciones}", estado="alerta")
                break
            iteraciones += 1
            r = _consultar(fuente, sql, traza, cfg)
            evidencia.append({"id": f"E{len(evidencia) + 1}", "sql": " ".join(sql.split()),
                              "motor": r.get("motor"), "ok": bool(r.get("ok")), "filas": r.get("filas", []),
                              "n_filas": int(r.get("n_filas", 0)), "error": r.get("error")})

        traza.evento("investigador", "modelo", "proponer_hipotesis", entrada=pregunta,
                     salida="omitido: el investigador llega en el Paso 10 (JPTRS-67)", estado="omitido")

        if llm.costo_usd > cfg.presupuesto_usd:
            traza.evento("orquestador", "modelo", "alerta_gasto",
                         salida=f"gasto {llm.costo_usd:.4f} USD > presupuesto {cfg.presupuesto_usd} USD",
                         estado="alerta")

        respuesta = {
            "version": "0.1", "run_id": run_id, "pregunta": pregunta, "modo": cfg.modo,
            "estado": "abstencion", "conclusion": None, "hipotesis": [], "evidencia": evidencia,
            "recomendacion": None, "abstencion": {"razon": RAZON_ESQUELETO},
            "aprobacion": {"item_id": "", "estado": "pendiente"},
            "metricas": {"iteraciones": iteraciones, "consultas": len(evidencia), "ms": 0.0,
                         "tokens": llm.tokens, "costo_usd": round(llm.costo_usd, 6)},
            "informe_md": "",
        }

        item = cola_mod.ColaAprobacion(cfg.logs).encolar(
            run_id, respuesta["conclusion"] or respuesta["abstencion"]["razon"], cfg.modo_muestra)
        contrato.validar_aprobacion(item)
        traza.evento("cola", "cola_aprobacion", "encolar", entrada=item["resumen"],
                     salida=f"{item['item_id']} · {item['estado']}"
                            + (f" por {item['decidido_por']}" if item["decidido_por"] else ""))
        respuesta["aprobacion"] = {"item_id": item["item_id"], "estado": item["estado"]}

    respuesta["metricas"]["ms"] = round(total.ms, 1)
    respuesta["informe_md"] = contrato.informe(respuesta)
    contrato.validar_respuesta(respuesta)

    cfg.salidas.mkdir(parents=True, exist_ok=True)
    (cfg.salidas / f"{run_id}.json").write_text(json.dumps(respuesta, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    (cfg.salidas / f"{run_id}.md").write_text(respuesta["informe_md"], encoding="utf-8")
    traza.evento("orquestador", "salida", "entregar", entrada=respuesta["estado"],
                 salida=f"salidas/{run_id}.json + .md")
    return respuesta
