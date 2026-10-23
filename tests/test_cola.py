"""Paso 11: separar disputas, redactar respuestas y la cola con su política. Sin red."""

import json

import pytest

from agente import cola, contrato, datos, preparador
from agente import orquestador as orq
from tests.conftest import leer_jsonl
from tests.falsos import GRUPO, GUION_CASO3, PICO, ModeloGuion, MotorFalso

PICO_QUINCENA = "¿Por qué subieron las disputas en la segunda quincena de septiembre de 2026?"


@pytest.fixture
def real(entorno, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "false")

    def correr(guion, respuestas=PICO, pregunta=PICO_QUINCENA):
        m = ModeloGuion(guion)
        monkeypatch.setattr(orq.modelo, "crear", lambda cfg, turnos=None: m)
        monkeypatch.setattr(orq.datos, "crear", lambda cfg, extra=None: MotorFalso(respuestas))
        return orq.correr(pregunta)
    return correr


def items(entorno):
    return leer_jsonl(entorno / "logs" / "cola_aprobacion.jsonl")


def test_el_periodo_sale_de_la_pregunta():
    assert preparador.periodo(PICO_QUINCENA)[:2] == ("2026-09-16", "2026-10-01")
    assert preparador.periodo("¿y en la primera quincena de diciembre de 2026?")[:2] == ("2026-12-01", "2026-12-16")
    assert preparador.periodo("¿Qué pasó en agosto de 2026?")[:2] == ("2026-08-01", "2026-09-01")
    assert preparador.periodo("¿Por qué subieron?") is None


@pytest.mark.parametrize("cambio, regla", [
    ({}, None),
    ({"senales_fraude": 1}, "sin_senales_fraude"),
    ({"estado": "won"}, "disputa_abierta"),
    ({"monto": 900}, "monto_tope"),
    ({"reclamo_previo": True}, "evidencia_completa"),
    ({"prueba_entrega": "ninguna"}, "evidencia_completa"),
])
def test_la_politica_aprueba_solo_lo_que_no_tiene_dudas(cambio, regla):
    d = {**GRUPO[0], **cambio}
    entrada = {"tipo": "respuesta_banco", "disputa_id": d["disputa_id"], "datos": d, "evidencia": ["E3"],
               "borrador": preparador.borrador_banco(d, [], "E3", None)}
    estado, motivo, reglas = cola.decidir(entrada)
    fallan = [r["regla"] for r in reglas if not r["ok"]]
    if regla is None:
        assert estado == "aprobada" and not fallan
    else:
        assert estado == "rechazada" and fallan == [regla] and motivo


def test_un_borrador_que_no_cita_su_evidencia_se_rechaza():
    entrada = {"tipo": "respuesta_banco", "disputa_id": "du_A1", "datos": GRUPO[0], "evidencia": ["E3"],
               "borrador": "Solicitamos que se mantenga el cargo."}
    estado, motivo, _ = cola.decidir(entrada)
    assert estado == "rechazada" and "no cita la evidencia" in motivo


def test_el_grupo_tiene_su_causa_sus_respuestas_y_una_rechazada_en_logs(entorno, real):
    r = real(GUION_CASO3)
    contrato.validar_respuesta(r)
    cola_corrida = {(c["tipo"], c["disputa_id"]): c for c in r["cola"]}
    assert cola_corrida[("grupo", None)]["estado"] == "aprobada"
    assert "du_C3" in cola_corrida[("grupo", None)]["borrador"]  # la que no conviene pelear, con qué hacer
    assert cola_corrida[("respuesta_banco", "du_A1")]["estado"] == "aprobada"
    rechazada = cola_corrida[("respuesta_banco", "du_B2")]
    assert rechazada["estado"] == "rechazada" and "señales de fraude" in rechazada["motivo"]
    assert ("respuesta_banco", "du_C3") not in cola_corrida  # no se redacta lo que no vale pelear
    # lo que vale pelear en el período tiene su respuesta aunque no sea del grupo de la causa
    assert cola_corrida[("respuesta_banco", "du_D4")]["estado"] == "aprobada"
    grupo = cola_corrida[("grupo", None)]["borrador"]
    assert "De las 3 disputas de RapidEnvio · Norte en la segunda quincena" in grupo
    assert "Fuera de ese grupo hay 1 disputa más" in grupo
    # todo queda en logs: cada ítem con su regla, su motivo y su borrador
    for item in items(entorno):
        contrato.validar_aprobacion(item)
        assert item["decidido_por"] == "regla:politica_v1" and item["motivo"]
    linea = next(i for i in items(entorno) if i["disputa_id"] == "du_B2")
    assert {"regla": "sin_senales_fraude", "ok": False, "detalle": "1 señal(es) de fraude"} in linea["reglas"]
    traza = leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")
    assert any(e["accion"] == "encolar" and e["estado"] == "alerta" and "du_B2" in e["entrada"] for e in traza)
    # las consultas de la cola son evidencia como cualquier otra, y la de las disputas filtra por el período
    sql = next(e["sql"] for e in r["evidencia"] if "disputa_id, pedido_id" in e["sql"])
    assert "TIMESTAMP '2026-09-16 00:00:00'" in sql and "TIMESTAMP '2026-10-01 00:00:00'" in sql
    assert "### Cola de aprobación" in r["informe_md"] and "⛔ rechazada" in r["informe_md"]


def test_una_disputa_que_no_vale_pelear_queda_como_no_pelear(entorno, real):
    fraude = {**GRUPO[1], "disputa_id": "du_LRbXAOhoJgujrS", "senales_fraude": 4, "vale_pelear": False,
              "razon_decision": "sospecha_de_fraude"}
    concluir = {"accion": "concluir", "conclusion": "No conviene pelearla: hay 4 señales de fraude.",
                "recomendacion": "No pelear y marcar al cliente."}
    r = real([*GUION_CASO3[:5], concluir], {"disputa_id IN ('du_LRbXAOhoJgujrS')": [fraude], **PICO},
             "¿Vale la pena pelear la disputa du_LRbXAOhoJgujrS?")
    (entrada,) = r["cola"]
    assert entrada["tipo"] == "no_pelear" and entrada["estado"] == "aprobada"
    assert "señales de fraude" in entrada["borrador"] and "aceptar la disputa y marcar al cliente" in entrada["borrador"]


def test_sin_world_model_no_se_puede_delimitar_el_grupo(entorno, real, monkeypatch):
    monkeypatch.setenv("AGENTE_MUNDO", "false")
    r = real(GUION_CASO3)
    (grupo,) = r["cola"]
    assert grupo["tipo"] == "grupo" and grupo["estado"] == "rechazada"
    assert "World Model está apagado" in grupo["borrador"]


def test_una_abstencion_no_prepara_respuestas(entorno, real):
    r = real([GUION_CASO3[0], {"accion": "abstenerse", "razon": "no alcanza"}])
    assert r["cola"] == []
    (item,) = items(entorno)
    assert item["tipo"] == "conclusion" and item["estado"] == "rechazada"


def test_el_modo_de_muestra_completa_lo_que_le_falta(tmp_path, monkeypatch):
    muestras = tmp_path / "consultas.json"
    muestras.write_text(json.dumps({"origen": "prueba", "consultas": {"SELECT 1": {"ok": True, "filas": []}}}),
                        encoding="utf-8")
    monkeypatch.setenv("AGENTE_MUESTRAS", str(muestras))
    monkeypatch.setenv("AGENTE_COMPLETAR_MUESTRAS", "true")
    monkeypatch.setattr(datos.FuenteMotor, "consultar",
                        lambda self, sql: {"ok": True, "motor": "duckdb", "filas": [{"n": 1}], "n_filas": 1, "ms": 3})
    fuente = datos.crear(orq.config_mod.cargar())
    assert fuente.consultar("SELECT  2")["filas"] == [{"n": 1}]
    grabadas = json.loads(muestras.read_text(encoding="utf-8"))["consultas"]
    assert "SELECT 2" in grabadas and "ms" not in grabadas["SELECT 2"]
