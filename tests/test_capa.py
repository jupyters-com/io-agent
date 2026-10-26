"""Paso 12: el interruptor SEMANTIC_LAYER apaga la capa de IO (esquema canónico, definiciones y Meterless)."""

import json

import pytest

from agente import evaluador
from agente import orquestador as orq
from tests.conftest import leer_jsonl
from tests.falsos import GUION_CASO3, PICO, ModeloGuion, MotorFalso

PREGUNTA = "¿Por qué subieron las disputas?"


class ModeloQueGuarda(ModeloGuion):
    def completar(self, mensajes):
        self.sistema = mensajes[0]["content"]
        self.primero = getattr(self, "primero", None) or mensajes[1]["content"]
        return super().completar(mensajes)


@pytest.fixture
def real(entorno, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "false")

    def correr(guion, pregunta=PREGUNTA):
        m = ModeloQueGuarda(guion)
        monkeypatch.setattr(orq.modelo, "crear", lambda cfg, turnos=None: m)
        monkeypatch.setattr(orq.datos, "crear", lambda cfg, extra=None: MotorFalso(PICO))
        return orq.correr(pregunta), m
    return correr


def eventos(entorno, r):
    return leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")


def test_con_la_capa_el_modelo_ve_el_esquema_canonico_y_sus_definiciones(entorno, real):
    r, m = real(GUION_CASO3)
    assert "canonico.disputas" in m.sistema and "razon_decision" in m.sistema and "crudo." not in m.sistema
    assert r["metricas"]["capa_semantica"] == "on"


def test_sin_la_capa_solo_ve_las_tablas_crudas_y_nada_de_io(entorno, real, monkeypatch):
    monkeypatch.setenv("SEMANTIC_LAYER", "off")
    r, m = real(GUION_CASO3, "¿Vale la pena pelear la disputa du_AAA?")
    assert "crudo.pagos_disputes" in m.sistema and "crudo.soporte_tickets" in m.sistema
    for de_io in ("canonico.", "razon_decision", "vale_pelear", "sospecha_fraude", "Recomendaciones de IO"):
        assert de_io not in m.sistema
    assert "id de crudo.pagos_disputes" in m.primero
    assert r["metricas"]["capa_semantica"] == "off" and r["metricas"]["memorias_usadas"] == 0
    ev = eventos(entorno, r)
    assert "capa=off" in ev[0]["salida"]
    # sin Meterless y sin la cola: todo queda marcado como omitido en la traza
    assert all(e["estado"] == "omitido" for e in ev if e["agente"] in ("memoria", "mundo"))
    assert any(e["accion"] == "preparar" and e["estado"] == "omitido" for e in ev)
    assert r["cola"] == []


def test_sin_la_capa_el_evaluador_no_pide_contar_decisiones_que_no_existen():
    hip = {"H1": {"id": "H1", "veredicto": "sostenida", "razon": "x", "evidencia": ["E1"]},
           "H2": {"id": "H2", "veredicto": "descartada", "razon": "y", "evidencia": ["E1"]}}
    ev = {"E1": {"id": "E1", "ok": True, "n_filas": 1, "sql": "SELECT 1", "filas": [{"n": 1}]}}
    rec = "Pelear las 14 disputas."
    assert any("contó sus decisiones" in p for p in evaluador.revisar_conclusion(hip, ev, "Causa.", rec))
    assert evaluador.revisar_conclusion(hip, ev, "Causa.", rec, capa=False) == []


def test_las_corridas_sin_capa_se_graban_aparte_y_no_se_mezclan(entorno, real, monkeypatch, tmp_path):
    muestras = tmp_path / "samples" / "consultas.json"
    muestras.parent.mkdir()
    muestras.write_text(json.dumps({"origen": "prueba", "consultas": {}}), encoding="utf-8")
    monkeypatch.setenv("AGENTE_MUESTRAS", str(muestras))
    monkeypatch.setenv("AGENTE_GRABAR", "true")
    monkeypatch.setenv("AGENTE_HMEM", "false")
    real(GUION_CASO3)
    monkeypatch.setenv("SEMANTIC_LAYER", "off")
    real([GUION_CASO3[0], {"accion": "abstenerse", "razon": "con las tablas crudas no alcanza"}])
    nombres = sorted(p.name for p in (tmp_path / "samples" / "corridas").glob("*.json"))
    assert len(nombres) == 2 and sum(n.endswith("-sincapa.json") for n in nombres) == 1
    cfg = orq.config_mod.cargar()
    muestra = cfg.__class__(**{**cfg.__dict__, "modo_muestra": True})
    assert orq.corrida_grabada(muestra, PREGUNTA)["capa"] == "off"
    con = muestra.__class__(**{**muestra.__dict__, "capa_semantica": True})
    assert orq.corrida_grabada(con, PREGUNTA)["capa"] == "on"


def test_sin_la_capa_una_consulta_a_canonico_no_se_ejecuta(entorno, real, monkeypatch):
    """Aunque el modelo conozca el esquema canónico de otro lado (pasó con Nightshift), no lo puede usar."""
    monkeypatch.setenv("SEMANTIC_LAYER", "off")
    r, m = real([GUION_CASO3[0], GUION_CASO3[1], {"accion": "abstenerse", "razon": "no alcanza"}])
    (e,) = r["evidencia"]
    assert not e["ok"] and "capa de IO" in e["error"] and "crudo" in e["error"]
    assert any("SEMANTIC_LAYER=off" in msg for msg in m.recibidos)


def test_sin_la_capa_nightshift_ve_otra_app():
    from agente import config, modelo
    cfg = config.cargar()
    con = modelo.crear(cfg.__class__(**{**cfg.__dict__, "modo_muestra": False}))
    sin = modelo.crear(cfg.__class__(**{**cfg.__dict__, "modo_muestra": False, "capa_semantica": False}))
    assert con.app == "io-agent" and sin.app == "io-agent-sin-capa"
