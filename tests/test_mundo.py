"""World Model (Meterless) dentro del agente: ids estables, ingesta idempotente, anclaje y respaldo. Sin red."""

import json

import pytest

from agente import mundo as wm
from agente import orquestador as orq
from tests.conftest import leer_jsonl
from tests.falsos import GUION_CASO3, PICO, ModeloGuion, MotorFalso

PREGUNTA = "¿Por qué subieron las disputas?"
FUENTE = {"kind": "agent", "by": "prueba", "at": "2026-10-23T00:00:00Z", "runId": "r1", "ref": "E1"}
FILAS = [{"disputa_id": "du_AAA", "pedido_id": "1574", "cliente_id": "c_9", "transportista": "RapidEnvio",
          "region": "Norte", "razon_decision": "reclamo_previo"}]


@pytest.fixture
def real(entorno, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "false")

    def correr(guion, respuestas=PICO, pregunta=PREGUNTA):
        m = ModeloGuion(guion)
        monkeypatch.setattr(orq.modelo, "crear", lambda cfg, turnos=None: m)
        monkeypatch.setattr(orq.datos, "crear", lambda cfg, extra=None: MotorFalso(respuestas))
        return orq.correr(pregunta), m
    return correr


def eventos(entorno, r, accion=None):
    ev = leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")
    return [e for e in ev if accion is None or e["accion"] == accion]


def test_los_ids_son_estables_y_derivados_del_contenido():
    assert wm.id_entidad("disputa", "du_AAA") == "disputa:io:du_AAA"
    assert wm.id_entidad("transportista", nombre="Rápid  Envío") == wm.id_entidad("transportista", nombre="rapid envio")
    assert wm.id_entidad("region", nombre="Norte").startswith("ent_")


def test_la_ingesta_es_idempotente_y_el_estado_es_un_fold_de_los_eventos(tmp_path):
    mundo = wm.WorldModel(tmp_path)
    primera = wm.ingerir_filas(mundo, FILAS, "corrida:io:r1", FUENTE)
    segunda = wm.ingerir_filas(mundo, FILAS, "corrida:io:r1", FUENTE)
    assert primera["nuevos"] > 0 and segunda["nuevos"] == 0
    otra_vez = wm.WorldModel(tmp_path)  # se reconstruye solo desde eventos.jsonl
    assert otra_vez.entidades.keys() == mundo.entidades.keys() and otra_vez.hechos.keys() == mundo.hechos.keys()
    disputa = "disputa:io:du_AAA"
    assert {"pedido:io:1574", "cliente:io:c_9"} <= otra_vez.vecinos[disputa]
    hecho = next(h for h in otra_vez.hechos.values() if h["predicate"] == "razon_decision")
    assert hecho["about"] == disputa and hecho["value"] == "reclamo_previo" and hecho["source"]["ref"] == "E1"


def test_una_escritura_sin_procedencia_se_rechaza(tmp_path):
    with pytest.raises(wm.SinProcedencia):
        wm.WorldModel(tmp_path).upsert_entity("disputa", {}, clave_externa="du_X")


def test_la_conclusion_queda_anclada_a_la_evidencia_de_la_corrida(entorno, real):
    r, _ = real(GUION_CASO3)
    assert r["estado"] == "concluida" and r["metricas"]["entidades_ancladas"] == 2
    (anclar,) = eventos(entorno, r, "anclar")
    assert anclar["agente"] == "mundo" and anclar["estado"] == "ok" and "RapidEnvio (E2)" in anclar["salida"]


def test_nombrar_algo_que_esta_corrida_no_consulto_se_devuelve(entorno, real):
    real(GUION_CASO3)  # el mundo ya conoce RapidEnvio, Norte y Sur
    solo_norte = {**PICO, "transportista, region": PICO["transportista, region"][:1]}
    invento = {"accion": "concluir", "conclusion": "Lo explica RapidEnvio en el Norte y en el Sur (14 de 18).",
               "recomendacion": "Reclamar a RapidEnvio."}
    r, m = real([*GUION_CASO3[:5], invento, GUION_CASO3[5]], solo_norte)
    assert r["estado"] == "concluida" and r["metricas"]["devoluciones"] == 1
    assert any("región Sur" in msg and "no es evidencia" in msg for msg in m.recibidos)
    anclas = eventos(entorno, r, "anclar")
    assert [e["estado"] for e in anclas] == ["alerta", "ok"]


def test_sin_world_model_esa_conclusion_pasaba(entorno, real, monkeypatch):
    real(GUION_CASO3)
    monkeypatch.setenv("AGENTE_MUNDO", "false")
    solo_norte = {**PICO, "transportista, region": PICO["transportista, region"][:1]}
    invento = {"accion": "concluir", "conclusion": "Lo explica RapidEnvio en el Norte y en el Sur (14 de 18).",
               "recomendacion": "Reclamar a RapidEnvio."}
    r, _ = real([*GUION_CASO3[:5], invento], solo_norte)
    assert r["estado"] == "concluida" and "Sur" in r["conclusion"]  # lo que el World Model evita
    assert all(e["estado"] == "omitido" for e in eventos(entorno, r) if e["agente"] == "mundo")


def test_un_id_mal_escrito_recibe_el_id_canonico(entorno, real):
    pregunta = "¿Vale la pena pelear la disputa du_LRbXAOhoJgujrS?"
    guion = [GUION_CASO3[0], {"accion": "consultar", "hipotesis": "H1",
                              "sql": "SELECT * FROM canonico.disputas WHERE disputa_id = 'du_LRbXAOhoJgujrs'"},
             {"accion": "abstenerse", "razon": "no la encontré"}]
    r, m = real(guion, {"du_LRbXAOhoJgujrs": []}, pregunta)
    assert "WORLD MODEL: du_LRbXAOhoJgujrs no existe; el id canónico es du_LRbXAOhoJgujrS" in m.recibidos[2]
    (resolver,) = eventos(entorno, r, "resolver")
    assert resolver["agente"] == "mundo"


def test_si_el_world_model_falla_el_agente_sigue_con_el_respaldo(entorno, real, monkeypatch):
    def roto(*a, **k):
        raise OSError("disco lleno")
    monkeypatch.setattr(wm.WorldModel, "vistos_en", roto)
    r, _ = real(GUION_CASO3)
    assert r["estado"] == "concluida"
    (e,) = eventos(entorno, r, "anclar")
    assert e["estado"] == "error" and "respaldo" in e["salida"]
