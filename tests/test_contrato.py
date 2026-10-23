"""El contrato del agente y el esqueleto: deben pasar desde hoy (Paso 9)."""

import copy
import json

import pytest

from agente import config, contrato, modelo
from agente import orquestador as orq
from agente.datos import FuenteMuestra
from tests.conftest import leer_jsonl, pregunta
from tests.falsos import GUION_CASO3, ModeloGuion

CASOS = ["caso1", "caso2", "caso3"]


@pytest.mark.parametrize("caso", CASOS)
def test_modo_muestra_corre_sin_credenciales_y_cumple_el_contrato(entorno, caso):
    r = orq.correr(pregunta(caso))
    contrato.validar_respuesta(r)
    assert r["modo"] == "muestra"
    assert (entorno / "salidas" / f"{r['run_id']}.json").exists()
    assert (entorno / "salidas" / f"{r['run_id']}.md").read_text(encoding="utf-8") == r["informe_md"]


def test_la_traza_cumple_su_esquema_y_cuenta_la_corrida(entorno):
    r = orq.correr(pregunta("caso3"))
    eventos = leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")
    for e in eventos:
        contrato.validar_evento(e)
    assert [e["paso"] for e in eventos] == list(range(1, len(eventos) + 1))
    acciones = [e["accion"] for e in eventos]
    assert acciones[0] == "recibir_pregunta" and acciones[-1] == "entregar"
    assert "pensar" in acciones and "encolar" in acciones


def test_en_modo_muestra_una_regla_aprueba_y_queda_registrado(entorno):
    r = orq.correr(pregunta("caso1"))
    item = leer_jsonl(entorno / "logs" / "cola_aprobacion.jsonl")[0]
    contrato.validar_aprobacion(item)
    esperado = "aprobada" if r["estado"] == "concluida" else "rechazada"
    assert item["tipo"] == "conclusion" and item["estado"] == esperado and item["decidido_por"] == "regla:politica_v1"
    assert r["aprobacion"] == {"item_id": item["item_id"], "estado": esperado}


def test_sin_corrida_grabada_el_agente_se_abstiene_en_vez_de_inventar(entorno, monkeypatch):
    monkeypatch.setattr(orq, "corrida_grabada", lambda cfg, p, con_memoria=False: None)
    r = orq.correr(pregunta("caso3"))
    assert r["estado"] == "abstencion" and r["conclusion"] is None and r["abstencion"]["razon"]
    assert "IO no da una conclusión" in r["informe_md"]


# --- Reglas del contrato que el esquema solo no puede expresar ---

@pytest.fixture
def concluida():
    r = {
        "version": "0.1", "run_id": "t", "pregunta": "¿Por qué?", "modo": "muestra",
        "estado": "concluida", "conclusion": "Fue el transportista.",
        "hipotesis": [
            {"id": "H1", "enunciado": "Atrasos de RapidEnvio en el Norte", "veredicto": "sostenida",
             "razon": "14 de 14 disputas con envío tarde", "evidencia": ["E1"]},
            {"id": "H2", "enunciado": "Ola de fraude", "veredicto": "descartada",
             "razon": "Las señales de fraude no subieron", "evidencia": ["E1"]},
        ],
        "evidencia": [{"id": "E1", "sql": "SELECT 1", "motor": "duckdb", "ok": True,
                       "filas": [{"n": 14}], "n_filas": 1, "error": None}],
        "recomendacion": "Reclamar al transportista.", "abstencion": None,
        "aprobacion": {"item_id": "AP-t", "estado": "aprobada"}, "cola": [],
        "metricas": {"iteraciones": 1, "consultas": 1, "ms": 1.0, "tokens": 0, "costo_usd": 0.0},
        "informe_md": "",
    }
    r["informe_md"] = contrato.informe(r)
    return r


def test_una_respuesta_concluida_bien_formada_pasa(concluida):
    contrato.validar_respuesta(concluida)
    assert "~~Ola de fraude~~" in concluida["informe_md"]


@pytest.mark.parametrize("romper, mensaje", [
    (lambda r: r["hipotesis"].__setitem__(0, {**r["hipotesis"][0], "veredicto": "sin_decidir"}),
     "al menos una hipótesis sostenida"),
    (lambda r: r["hipotesis"][0].__setitem__("evidencia", ["E9"]), "E9, que no existe"),
    (lambda r: r["hipotesis"][1].__setitem__("evidencia", []), "descartada sin evidencia"),
    (lambda r: r["evidencia"][0].__setitem__("ok", False), "consulta fallida"),
    (lambda r: r.update(estado="abstencion", abstencion={"razon": "x"}), "abstención no puede traer conclusión"),
    (lambda r: r.update(informe_md="sin secciones"), "le falta la sección"),
    (lambda r: r.update(extra=1), "Additional properties"),
])
def test_el_contrato_rechaza_respuestas_mal_formadas(concluida, romper, mensaje):
    r = copy.deepcopy(concluida)
    romper(r)
    with pytest.raises(contrato.ContratoRoto, match=mensaje):
        contrato.validar_respuesta(r)


def test_aprobacion_decidida_sin_quien_se_rechaza():
    item = {"item_id": "AP-x", "run_id": "x", "tipo": "conclusion", "estado": "aprobada",
            "creado_en": "t", "decidido_en": "t", "decidido_por": None, "motivo": None, "resumen": "r"}
    with pytest.raises(contrato.ContratoRoto, match="quién lo decidió"):
        contrato.validar_aprobacion(item)


# --- Topes ---

def test_tope_de_iteraciones_queda_como_alerta(entorno, monkeypatch):
    monkeypatch.setenv("AGENTE_MAX_ITERACIONES", "0")
    r = orq.correr(pregunta("caso3"))
    eventos = leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")
    assert any(e["accion"] == "tope_iteraciones" and e["estado"] == "alerta" for e in eventos)
    assert r["metricas"]["consultas"] == 0


def test_timeout_del_motor_reintenta_una_vez_y_no_rompe_la_corrida(entorno, monkeypatch):
    class MotorLento:
        nombre = "io-engine"
        llamadas = 0

        def consultar(self, sql):
            MotorLento.llamadas += 1
            raise TimeoutError("io-engine no respondió en 60 s")

    monkeypatch.setattr(orq.datos, "crear", lambda cfg, extra=None: MotorLento())
    monkeypatch.setattr(orq.modelo, "crear", lambda cfg, turnos=None: ModeloGuion(
        [GUION_CASO3[0], GUION_CASO3[1], {"accion": "abstenerse", "razon": "El motor no responde."}]))
    r = orq.correr(pregunta("caso3"))
    contrato.validar_respuesta(r)
    assert MotorLento.llamadas == 2
    (consulta,) = [e for e in leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl") if e["accion"] == "consultar"]
    assert consulta["estado"] == "error" and consulta["reintentos"] == 1
    assert r["estado"] == "abstencion" and r["evidencia"][0]["ok"] is False


def test_alerta_de_gasto(entorno, monkeypatch):
    caro = ModeloGuion([{"accion": "abstenerse", "razon": "prueba"}])
    caro.costo_usd = 5.0
    monkeypatch.setenv("AGENTE_PRESUPUESTO_USD", "1")
    monkeypatch.setattr(orq.modelo, "crear", lambda cfg, turnos=None: caro)
    r = orq.correr(pregunta("caso3"))
    eventos = leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")
    assert any(e["accion"] == "alerta_gasto" and e["estado"] == "alerta" for e in eventos)


def test_consulta_fuera_de_la_muestra_no_rompe(entorno):
    r = FuenteMuestra(config.cargar().muestras).consultar("SELECT 42")
    assert r["ok"] is False and "fuera de la muestra" in r["error"]


def test_nightshift_manda_el_contrato_de_meterless_y_cuenta_tokens():
    m = modelo.ModeloNightshift("http://127.0.0.1:8088/v1", "token-prueba", "nvidia/nemotron", 5)
    enviado = {}

    def falso_post(cuerpo):
        enviado.update(cuerpo)
        return {"model": "nvidia/nemotron", "choices": [{"message": {"content": "hola"}}],
                "usage": {"total_tokens": 99, "cost": 0.0}}

    m._post = falso_post
    r = m.completar([{"role": "user", "content": "hola"}])
    assert enviado["model"] == "nvidia/nemotron" and r["texto"] == "hola"
    assert m.tokens == 99


def test_las_muestras_vienen_de_io_engine_no_de_la_mano():
    datos = json.loads(config.cargar().muestras.read_text(encoding="utf-8"))
    assert datos["origen"].startswith("io-engine en ")
    assert all(c["motor"] in ("duckdb", "zetaris") for c in datos["consultas"].values())
