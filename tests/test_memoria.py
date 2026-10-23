"""H-MEM (Meterless) dentro del agente: aprende, recuerda, se puede apagar y tiene respaldo. Sin red."""

import json
import time

import pytest

from agente import memoria as hmem
from agente import orquestador as orq
from tests.conftest import leer_jsonl
from tests.falsos import GUION_CASO3, PICO, ModeloGuion, MotorFalso

PREGUNTA = "¿Por qué subieron las disputas?"
# Concluye sin haber probado la segunda hipótesis: el Evaluador la devuelve una vez.
APURADO = [GUION_CASO3[0], GUION_CASO3[1], GUION_CASO3[2], GUION_CASO3[5], *GUION_CASO3[3:]]


@pytest.fixture
def real(entorno, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "false")
    modelos = []

    def correr(guion, pregunta=PREGUNTA):
        m = ModeloGuion(guion)
        modelos.append(m)
        monkeypatch.setattr(orq.modelo, "crear", lambda cfg, turnos=None: m)
        monkeypatch.setattr(orq.datos, "crear", lambda cfg, extra=None: MotorFalso(PICO))
        return orq.correr(pregunta), m
    return correr


def eventos(entorno, r, accion=None):
    ev = leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")
    return [e for e in ev if accion is None or e["accion"] == accion]


def guardado(entorno):
    return json.loads((entorno / "memoria" / "memorias.json").read_text(encoding="utf-8"))["records"]


def test_la_leccion_del_evaluador_se_recuerda_en_la_corrida_siguiente(entorno, real):
    r1, m1 = real(APURADO)
    assert r1["estado"] == "concluida" and r1["metricas"]["devoluciones"] == 1
    assert "MEMORIA DE IO" not in m1.recibidos[0]  # la primera vez no hay nada que recordar
    (aprender,) = eventos(entorno, r1, "aprender")
    assert "nuevas" in aprender["salida"]
    lecciones = [m for m in guardado(entorno) if m["type"] == "preference"]
    assert lecciones and all(m["source"] == f"corrida:{r1['run_id']}" for m in lecciones)
    assert any("al menos 2 hipótesis" in m["content"] for m in lecciones)

    r2, m2 = real(GUION_CASO3)
    assert "MEMORIA DE IO (H-MEM)" in m2.recibidos[0] and "Lección del Evaluador" in m2.recibidos[0]
    assert r2["metricas"]["memorias_usadas"] >= 1 and r2["metricas"]["devoluciones"] == 0
    (recordar,) = eventos(entorno, r2, "recordar")
    assert recordar["agente"] == "memoria" and recordar["estado"] == "ok" and "0 lecciones" not in recordar["salida"]
    # no se repitió el error: la lección queda reforzada (+0.05, el delta exacto de H-MEM)
    for leccion in (m for m in guardado(entorno) if m["type"] == "preference"):
        assert leccion["confidence"] == pytest.approx(0.85)


def test_los_hallazgos_se_recuerdan_para_la_misma_pregunta_y_se_reemplazan(entorno, real):
    r1, _ = real(GUION_CASO3)
    hallazgos = [m for m in guardado(entorno) if m["type"] == "factual"]
    assert len(hallazgos) == 3  # la conclusión y las dos hipótesis
    assert any("RapidEnvio" in m["content"] for m in hallazgos)

    r2, m2 = real(GUION_CASO3)
    assert "RapidEnvio" in m2.recibidos[0] and "NO evidencia" in m2.recibidos[0]
    viejas = [m for m in guardado(entorno) if m["source"] == f"corrida:{r1['run_id']}" and m["type"] == "factual"]
    assert any(m["supersededBy"] for m in viejas)  # reemplazada, no borrada
    libro = leer_jsonl(entorno / "memoria" / "ledger.jsonl")
    assert {"create", "read", "feedback", "supersede"} <= {e["action"] for e in libro}


def test_lo_de_una_disputa_no_se_mezcla_con_otra(entorno, real):
    guion = [GUION_CASO3[0], GUION_CASO3[1], GUION_CASO3[2], GUION_CASO3[3], GUION_CASO3[4],
             {"accion": "concluir", "conclusion": "Vale la pena pelearla: llegó con firma.",
              "recomendacion": "Pelearla con la prueba de entrega."}]
    real(guion, "¿Vale la pena pelear la disputa du_AAAAAAAAAAAAAA?")
    _, m2 = real([GUION_CASO3[0], {"accion": "abstenerse", "razon": "no sé"}],
                 "¿Vale la pena pelear la disputa du_BBBBBBBBBBBBBB?")
    assert "du_AAAAAAAAAAAAAA" not in m2.recibidos[0]


def test_con_h_mem_apagado_corre_sin_memoria_y_lo_dice_la_traza(entorno, real, monkeypatch):
    real(APURADO)
    monkeypatch.setenv("AGENTE_HMEM", "false")
    r, m = real(APURADO)
    assert r["estado"] == "concluida" and r["metricas"]["memorias_usadas"] == 0
    assert "MEMORIA DE IO" not in m.recibidos[0]
    for accion in ("recordar", "aprender"):
        (e,) = eventos(entorno, r, accion)
        assert e["estado"] == "omitido" and "AGENTE_HMEM=false" in e["salida"]


def test_si_h_mem_falla_el_agente_sigue_con_el_respaldo(entorno, real, monkeypatch):
    def roto(*a, **k):
        raise OSError("disco lleno")
    monkeypatch.setattr(hmem.HMEM, "recordar", roto)
    r, m = real(GUION_CASO3)
    assert r["estado"] == "concluida"
    (e,) = eventos(entorno, r, "recordar")
    assert e["estado"] == "error" and "respaldo" in e["salida"] and "disco lleno" in e["salida"]


def test_si_h_mem_tarda_demasiado_el_agente_no_lo_espera(entorno, real, monkeypatch):
    monkeypatch.setenv("AGENTE_HMEM_TIMEOUT_S", "0.2")
    monkeypatch.setattr(hmem.HMEM, "recordar", lambda *a, **k: time.sleep(2))
    inicio = time.perf_counter()
    r, _ = real(GUION_CASO3)
    assert time.perf_counter() - inicio < 1.5
    (e,) = eventos(entorno, r, "recordar")
    assert e["estado"] == "error" and "tardó más de 0.2 s" in e["salida"]


def test_una_memoria_sin_fuente_se_rechaza(tmp_path):
    with pytest.raises(ValueError):
        hmem.HMEM(tmp_path).agregar("algo", "factual", "working", "", "disputas")


def test_la_corrida_con_memoria_se_graba_aparte(entorno, real, monkeypatch, tmp_path):
    muestras = tmp_path / "samples" / "consultas.json"
    muestras.parent.mkdir()
    muestras.write_text(json.dumps({"origen": "prueba", "consultas": {}}), encoding="utf-8")
    monkeypatch.setenv("AGENTE_MUESTRAS", str(muestras))
    monkeypatch.setenv("AGENTE_GRABAR", "true")
    real(APURADO)        # sin nada en memoria: variante normal
    real(GUION_CASO3)    # ya recuerda: variante -hmem
    archivos = sorted(p.name for p in (tmp_path / "samples" / "corridas").glob("*.json"))
    con_memoria = [a for a in archivos if a.endswith("-hmem.json")]
    assert len(archivos) == 2 and len(con_memoria) == 1
    grabada = json.loads((tmp_path / "samples" / "corridas" / con_memoria[0]).read_text(encoding="utf-8"))
    assert grabada["con_memoria"] and "Lección del Evaluador" in grabada["memoria"]

    cfg = orq.config_mod.cargar().__class__(**{**orq.config_mod.cargar().__dict__, "modo_muestra": True})
    assert orq.corrida_grabada(cfg, PREGUNTA, con_memoria=True)["con_memoria"] is True
    assert orq.corrida_grabada(cfg, PREGUNTA, con_memoria=False)["con_memoria"] is False


def test_la_reinyeccion_agrupa_por_dominio_con_capa_e_id(tmp_path):
    motor = hmem.HMEM(tmp_path)
    motor.agregar("Lección del Evaluador: cuenta las decisiones.", "preference", "long_term", "corrida:x", "metodo")
    motor.agregar("Para «¿Por qué?» IO concluyó: RapidEnvio en el Norte.", "factual", "working", "corrida:x", "disputas")
    texto = hmem.reinyectar([(m, 0.5) for m in motor.memorias.values()])
    assert "## disputas" in texto and "## metodo" in texto
    assert "[LT] Lección del Evaluador" in texto and "<mem-1>" in texto and "(entidades: rapidenvio, norte)" in texto


def test_las_lecciones_van_primero_y_piden_el_metodo_completo(tmp_path):
    motor = hmem.HMEM(tmp_path)
    motor.agregar("Para «¿Por qué?» IO concluyó: RapidEnvio.", "factual", "working", "corrida:x", "disputas")
    motor.agregar("Lección del Evaluador: cuenta las decisiones.", "preference", "working", "corrida:x", "metodo")
    texto = hmem.reinyectar([(m, 0.5) for m in motor.memorias.values()])
    assert texto.index("## metodo") < texto.index("## disputas")
    assert "método completo" in texto


def test_las_lecciones_quedan_como_reglas_generales():
    assert hmem._regla('La recomendación dice "reembolsar … 5", pero según E7 solo hay 4 disputa(s).') == \
        'La recomendación dice "…", pero según E# solo hay N disputa(s).'
    assert hmem._regla("Nombras la disputa du_cuKtmopzODI37h, pero ninguna consulta la devolvió.") == \
        "Nombras la disputa du_…, pero ninguna consulta la devolvió."
    assert "al menos 2 hipótesis" in hmem._regla("prueba al menos 2 hipótesis distintas")


def test_la_misma_leccion_con_otros_ejemplos_no_se_duplica():
    a = hmem._regla("La razón de H1 la lee la dueña: reescríbela sin términos técnicos (product_not_received).")
    b = hmem._regla("La razón de H3 la lee la dueña: reescríbela sin términos técnicos (causa_operativa, highest).")
    assert hmem._clave(a) == hmem._clave(b)
    assert hmem._clave(hmem._regla("Hay hipótesis sin veredicto: H2, H3.")) == \
        hmem._clave(hmem._regla("Hay hipótesis sin veredicto: H2, H3, H4."))
