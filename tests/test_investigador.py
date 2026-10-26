"""El ciclo del Investigador con un modelo de guion y un motor falso (sin red). Deben pasar."""

import json

import pytest

from agente import contrato
from agente import orquestador as orq
from tests.conftest import leer_jsonl
from tests.falsos import GUION_CASO3, PICO, ModeloGuion, MotorFalso


@pytest.fixture
def modo_real(entorno, monkeypatch):
    """Modo real, pero con el modelo y el motor reemplazados por falsos."""
    monkeypatch.setenv("SAMPLE_MODE", "false")

    def instalar(guion, respuestas=PICO):
        m = ModeloGuion(guion)
        monkeypatch.setattr(orq.modelo, "crear", lambda cfg, turnos=None: m)
        monkeypatch.setattr(orq.datos, "crear", lambda cfg, extra=None: MotorFalso(respuestas))
        return m
    return instalar


def eventos(entorno, r):
    return leer_jsonl(entorno / "logs" / f"{r['run_id']}.jsonl")


def test_ciclo_completo_descarta_una_hipotesis_con_su_evidencia(entorno, modo_real):
    modo_real(GUION_CASO3)
    r = orq.correr("¿Por qué subieron las disputas?")
    contrato.validar_respuesta(r)
    assert r["estado"] == "concluida" and "RapidEnvio" in r["conclusion"]
    h1, h2 = r["hipotesis"]
    assert h1["veredicto"] == "descartada" and h1["evidencia"] == ["E1"]
    assert h2["veredicto"] == "sostenida" and h2["evidencia"] == ["E2"]
    assert "~~El pico es una ola de fraude~~" in r["informe_md"]
    acciones = [e["accion"] for e in eventos(entorno, r)]
    assert acciones.count("consultar") == 2 and "descartar" in acciones and "sostener" in acciones
    assert "revisar_conclusion" in acciones
    for e in eventos(entorno, r):
        contrato.validar_evento(e)


def test_la_evidencia_queda_en_logs_con_sus_filas(entorno, modo_real):
    modo_real(GUION_CASO3)
    r = orq.correr("¿Por qué subieron las disputas?")
    filas = leer_jsonl(entorno / "logs" / f"{r['run_id']}.evidencia.jsonl")
    assert [f["id"] for f in filas] == ["E1", "E2"]
    assert filas[0]["hipotesis"] == "H1" and filas[0]["filas"] == PICO["senales_fraude"]


def test_el_evaluador_devuelve_un_veredicto_sin_evidencia_real(entorno, modo_real):
    guion = [GUION_CASO3[0], GUION_CASO3[1],
             {"accion": "veredicto", "hipotesis": "H1", "veredicto": "descartada", "razon": "no es", "evidencia": ["E9"]},
             *GUION_CASO3[2:]]
    m = modo_real(guion)
    r = orq.correr("¿Por qué subieron las disputas?")
    assert r["estado"] == "concluida"
    assert any("EVALUADOR" in msg and "E9" in msg for msg in m.recibidos)
    alertas = [e for e in eventos(entorno, r) if e["accion"] == "revisar_veredicto" and e["estado"] == "alerta"]
    assert len(alertas) == 1


def test_el_evaluador_no_deja_concluir_con_hipotesis_sin_veredicto(entorno, modo_real):
    guion = GUION_CASO3[:3] + [GUION_CASO3[5]] + GUION_CASO3[3:]
    m = modo_real(guion)
    r = orq.correr("¿Por qué subieron las disputas?")
    assert r["estado"] == "concluida"
    assert any("todavía no puedes concluir" in msg and "H2" in msg for msg in m.recibidos)


def test_respuesta_que_no_es_json_se_corrige_y_sigue(entorno, modo_real):
    m = modo_real(["Creo que es fraude, déjame pensar…", *GUION_CASO3])
    r = orq.correr("¿Por qué subieron las disputas?")
    assert r["estado"] == "concluida" and "ERROR" in m.recibidos[1]


def test_json_dentro_de_bloque_de_codigo_se_acepta(entorno, modo_real):
    guion = ["```json\n" + json.dumps(GUION_CASO3[0]) + "\n```", *GUION_CASO3[1:]]
    modo_real(guion)
    assert orq.correr("¿Por qué?")["estado"] == "concluida"


def test_consulta_que_falla_queda_como_evidencia_fallida(entorno, modo_real):
    guion = [GUION_CASO3[0], {"accion": "consultar", "hipotesis": "H1", "sql": "SELECT * FROM tabla_rara"},
             *GUION_CASO3[1:]]
    m = modo_real(guion)
    r = orq.correr("¿Por qué?")
    contrato.validar_respuesta(r)
    assert r["evidencia"][0]["ok"] is False and "falló" in m.recibidos[2]


def test_el_modelo_puede_abstenerse(entorno, modo_real):
    modo_real([GUION_CASO3[0], {"accion": "abstenerse", "razon": "No hay datos de envíos para esas fechas."}])
    r = orq.correr("¿Por qué?")
    contrato.validar_respuesta(r)
    assert r["estado"] == "abstencion" and "envíos" in r["abstencion"]["razon"]


def test_tope_de_vueltas_termina_en_abstencion(entorno, modo_real, monkeypatch):
    monkeypatch.setenv("AGENTE_MAX_ITERACIONES", "3")
    modo_real(GUION_CASO3)
    r = orq.correr("¿Por qué?")
    contrato.validar_respuesta(r)
    assert r["estado"] == "abstencion" and "tope de 3" in r["abstencion"]["razon"]
    assert any(e["accion"] == "tope_iteraciones" for e in eventos(entorno, r))


def test_modelo_caido_termina_en_abstencion(entorno, modo_real):
    modo_real([])  # el guion vacío lanza un error al primer pedido
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "abstencion" and "No pude hablar con el modelo" in r["abstencion"]["razon"]


def test_grabar_en_modo_real_y_repetir_en_modo_de_muestra(entorno, modo_real, monkeypatch, tmp_path):
    """La corrida real se graba y el modo de muestra la repite igual, sin modelo ni motor."""
    muestras = tmp_path / "samples" / "consultas.json"
    muestras.parent.mkdir()
    muestras.write_text(json.dumps({"origen": "io-engine en prueba", "consultas": {}}), encoding="utf-8")
    monkeypatch.setenv("AGENTE_MUESTRAS", str(muestras))
    monkeypatch.setenv("AGENTE_GRABAR", "true")
    modo_real(GUION_CASO3)
    real = orq.correr("¿Por qué subieron las disputas?")
    (grabada,) = (tmp_path / "samples" / "corridas").glob("*.json")
    assert len(json.loads(grabada.read_text(encoding="utf-8"))["turnos"]) == len(GUION_CASO3)

    monkeypatch.undo()  # quita los falsos
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("AGENTE_MUESTRAS", str(muestras))
    monkeypatch.setenv("AGENTE_LOGS", str(entorno / "logs"))
    monkeypatch.setenv("AGENTE_SALIDAS", str(entorno / "salidas"))
    repetida = orq.correr("¿Por qué subieron las disputas?")
    assert repetida["modo"] == "muestra"
    for campo in ("estado", "conclusion", "hipotesis", "evidencia", "recomendacion"):
        assert repetida[campo] == real[campo]


def test_pregunta_sin_corrida_grabada_se_abstiene_en_modo_de_muestra(entorno):
    r = orq.correr("¿Una pregunta que nadie grabó?")
    contrato.validar_respuesta(r)
    assert r["estado"] == "abstencion" and "No hay una corrida grabada" in r["abstencion"]["razon"]


def test_nightshift_reintenta_un_502_y_luego_responde():
    import io
    import urllib.error
    from agente.modelo import ModeloNightshift
    m = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron", 5, reintentos=2, espera_s=0)
    llamadas = []

    def post(cuerpo):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise urllib.error.HTTPError("u", 502, "Bad Gateway", {}, io.BytesIO(b"upstream timeout"))
        return {"model": "nvidia/nemotron", "choices": [{"message": {"content": "{}"}}], "usage": {}}

    m._post = post
    assert m.completar([{"role": "user", "content": "hola"}])["texto"] == "{}"
    assert m.reintentos_usados == 1


def test_nightshift_que_sigue_fallando_explica_el_error():
    import io
    import urllib.error
    from agente.modelo import ModeloNightshift
    m = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron", 5, reintentos=1, espera_s=0)

    def post(cuerpo):
        raise urllib.error.HTTPError("u", 502, "Bad Gateway", {}, io.BytesIO(b"upstream timeout"))

    m._post = post
    with pytest.raises(RuntimeError, match="HTTP 502 Bad Gateway: upstream timeout"):
        m.completar([{"role": "user", "content": "hola"}])


def test_si_el_modelo_falla_no_se_graba_la_corrida(entorno, modo_real, monkeypatch, tmp_path):
    muestras = tmp_path / "samples" / "consultas.json"
    muestras.parent.mkdir()
    muestras.write_text(json.dumps({"origen": "io-engine en prueba", "consultas": {}}), encoding="utf-8")
    monkeypatch.setenv("AGENTE_MUESTRAS", str(muestras))
    monkeypatch.setenv("AGENTE_GRABAR", "true")
    modo_real([])  # el modelo falla al primer pedido
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "abstencion"
    assert not (tmp_path / "samples" / "corridas").exists()
    assert any(e["accion"] == "grabar_corrida" and e["estado"] == "omitido" for e in eventos(entorno, r))


def test_varias_acciones_en_una_vuelta(entorno, modo_real):
    """Nemotron es lento: en 3 vueltas hace lo que antes tomaba 6."""
    g = GUION_CASO3
    m = modo_real([g[0], {"acciones": [g[1], g[3]]}, {"acciones": [g[2], g[4], g[5]]}])
    r = orq.correr("¿Por qué subieron las disputas?")
    contrato.validar_respuesta(r)
    assert r["estado"] == "concluida" and r["metricas"]["iteraciones"] == 3
    assert [e["id"] for e in r["evidencia"]] == ["E1", "E2"]
    assert "RESULTADO E1" in m.recibidos[2] and "RESULTADO E2" in m.recibidos[2]


def test_si_el_evaluador_rechaza_dentro_de_una_lista_el_resto_sigue(entorno, modo_real):
    g = GUION_CASO3
    malo = {"accion": "veredicto", "hipotesis": "H1", "veredicto": "descartada", "razon": "x", "evidencia": ["E7"]}
    m = modo_real([g[0], {"acciones": [g[1], g[3]]}, {"acciones": [malo, g[4], g[5]]}, {"acciones": [g[2], g[5]]}])
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "concluida"
    assert "EVALUADOR: no acepto" in m.recibidos[3] and "todavía no puedes concluir" in m.recibidos[3]


def test_sin_pensar_y_campos_extra_van_en_el_pedido():
    from agente.modelo import ModeloNightshift
    m = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron", 5, sin_pensar=True,
                         extra={"chat_template_kwargs": {"enable_thinking": False}})
    c = m.cuerpo([{"role": "system", "content": "Eres IO"}, {"role": "user", "content": "hola"}])
    assert c["messages"][0]["content"].startswith("/no_think\n") and c["messages"][1]["content"] == "hola"
    assert c["chat_template_kwargs"] == {"enable_thinking": False}


def test_stream_se_arma_como_una_respuesta_normal():
    import io
    from agente.modelo import ModeloNightshift, _juntar_stream
    sse = io.BytesIO(
        b'data: {"model": "nvidia/nemotron", "choices": [{"delta": {"content": "{\\"accion\\": "}}]}\n\n'
        b'data: {"model": "nvidia/nemotron", "choices": [{"delta": {"content": "\\"abstenerse\\"}"}}]}\n\n'
        b'data: {"model": "nvidia/nemotron", "choices": [], "usage": {"total_tokens": 42}}\n\n'
        b'data: [DONE]\n\n')
    r = _juntar_stream(sse)
    assert r["choices"][0]["message"]["content"] == '{"accion": "abstenerse"}'
    assert r["usage"]["total_tokens"] == 42
    m = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron", 5, stream=True)
    assert m.cuerpo([{"role": "user", "content": "hola"}])["stream"] is True


def test_nightshift_reintenta_si_se_pasa_del_tiempo():
    from agente.modelo import ModeloNightshift
    m = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron", 5, reintentos=1, espera_s=0)
    llamadas = []

    def post(cuerpo):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise TimeoutError("timed out")
        return {"model": "nvidia/nemotron", "choices": [{"message": {"content": "{}"}}], "usage": {}}

    m._post = post
    assert m.completar([{"role": "user", "content": "hola"}])["texto"] == "{}" and m.reintentos_usados == 1

    m2 = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron", 5, reintentos=1, espera_s=0)
    m2._post = lambda cuerpo: (_ for _ in ()).throw(TimeoutError("timed out"))
    with pytest.raises(RuntimeError, match="no respondió dentro de 5 s"):
        m2.completar([{"role": "user", "content": "hola"}])


def test_evidencia_citada_de_formas_raras_se_entiende(entorno, modo_real):
    g = GUION_CASO3
    v1 = {**g[2], "evidencia": ["E1 (fila de 0 señales)"]}
    v2 = {**g[4], "evidencia": "e2"}
    r = orq.correr("¿Por qué?") if modo_real([g[0], g[1], v1, g[3], v2, g[5]]) else None
    assert r["estado"] == "concluida"
    assert r["hipotesis"][0]["evidencia"] == ["E1"] and r["hipotesis"][1]["evidencia"] == ["E2"]


def test_una_abstencion_no_pisa_una_corrida_concluida(entorno, modo_real, monkeypatch, tmp_path):
    muestras = tmp_path / "samples" / "consultas.json"
    muestras.parent.mkdir()
    muestras.write_text(json.dumps({"origen": "io-engine en prueba", "consultas": {}}), encoding="utf-8")
    monkeypatch.setenv("AGENTE_MUESTRAS", str(muestras))
    monkeypatch.setenv("AGENTE_GRABAR", "true")
    modo_real(GUION_CASO3)
    orq.correr("¿Por qué subieron las disputas?")
    (archivo,) = (tmp_path / "samples" / "corridas").glob("*.json")
    buena = archivo.read_text(encoding="utf-8")
    assert json.loads(buena)["estado"] == "concluida"

    modo_real([GUION_CASO3[0], {"accion": "abstenerse", "razon": "no sé"}])
    r = orq.correr("¿Por qué subieron las disputas?")
    assert r["estado"] == "abstencion"
    assert archivo.read_text(encoding="utf-8") == buena  # la buena se conserva
    assert any(e["accion"] == "grabar_corrida" and e["estado"] == "omitido" for e in eventos(entorno, r))


def test_veredicto_sin_campo_evidencia_usa_la_consulta_de_esa_hipotesis(entorno, modo_real):
    """Nemotron a veces omite "evidencia": se toma la que menciona en la razón o la consulta que
    él mismo hizo para esa hipótesis, y queda anotado de dónde salió."""
    g = GUION_CASO3
    v1 = {k: v for k, v in g[2].items() if k != "evidencia"}
    v2 = {**{k: v for k, v in g[4].items() if k != "evidencia"}, "razon": "Según E2, 14 de 18 son de RapidEnvio"}
    modo_real([g[0], g[1], v1, g[3], v2, g[5]])
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "concluida"
    assert r["hipotesis"][0]["evidencia"] == ["E1"] and r["hipotesis"][1]["evidencia"] == ["E2"]
    revisiones = [e["entrada"] for e in eventos(entorno, r) if e["accion"] == "revisar_veredicto"]
    assert "consulta de la hipótesis" in revisiones[0] and "en la razón" in revisiones[1]


def test_evaluador_no_deja_recomendar_sin_contar_las_decisiones(entorno, modo_real):
    g = GUION_CASO3
    sin_decisiones = {**g[3], "sql": "SELECT transportista, region, count(*) AS disputas FROM canonico.disputas GROUP BY transportista, region"}
    concluir_otra_vez = dict(g[5])
    contar = {"accion": "consultar", "hipotesis": "H2",
              "sql": "SELECT transportista, region, razon_decision, count(*) FROM canonico.disputas GROUP BY 1, 2, 3"}
    m = modo_real([g[0], g[1], g[2], sin_decisiones, g[4], g[5], contar, concluir_otra_vez])
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "concluida"
    assert any("ninguna consulta contó sus decisiones" in msg for msg in m.recibidos)


def test_evaluador_devuelve_conclusiones_con_jerga(entorno, modo_real):
    g = GUION_CASO3
    con_jerga = {**g[5], "conclusion": "El pico es product_not_received con zona_con_atrasos=true en RapidEnvio."}
    m = modo_real([*g[:5], con_jerga, g[5]])
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "concluida" and "product_not_received" not in r["conclusion"]
    assert any("sin términos técnicos" in msg and "product_not_received" in msg for msg in m.recibidos)


def test_evaluador_rechaza_cantidades_que_no_cuadran_con_las_decisiones(entorno, modo_real):
    decisiones = [{"razon_decision": "entrega_confirmada_sin_reclamo", "cnt": 2},
                  {"razon_decision": "reclamo_previo", "cnt": 8}, {"razon_decision": "sin_entrega", "cnt": 4}]
    g = GUION_CASO3
    contar = {"accion": "consultar", "hipotesis": "H2",
              "sql": "SELECT razon_decision, count(*) AS cnt FROM canonico.disputas GROUP BY razon_decision"}
    mala = {**g[5], "recomendacion": "Pelear 14 de las 18 disputas y aceptar las 6 por fraude."}
    buena = {**g[5], "recomendacion": "Pelear 2, resolver con el cliente 8 y reembolsar 4; reclamar a RapidEnvio."}
    m = modo_real([g[0], g[1], g[2], contar, g[4], mala, buena], respuestas={**PICO, "razon_decision": decisiones})
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "concluida" and r["recomendacion"].startswith("Pelear 2")
    rechazo = next(msg for msg in m.recibidos if "no cuadra" in msg or "solo hay" in msg)
    assert "solo hay 2" in rechazo and "E2" in rechazo


def test_evaluador_exige_al_menos_dos_hipotesis_probadas(entorno, modo_real):
    g = GUION_CASO3
    una_sola = {"accion": "hipotesis", "hipotesis": [{"id": "H1", "enunciado": "Un transportista se atrasó"}]}
    consulta = {**g[3], "hipotesis": "H1"}
    veredicto = {**g[4], "hipotesis": "H1", "evidencia": ["E1"]}
    agregar = {"accion": "hipotesis", "hipotesis": [{"id": "H2", "enunciado": "El pico es una ola de fraude"}]}
    probar = {**g[1], "hipotesis": "H2"}
    descartar = {**g[2], "hipotesis": "H2", "evidencia": ["E2"]}
    m = modo_real([una_sola, consulta, veredicto, g[5], agregar, probar, descartar, g[5]])
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "concluida" and len(r["hipotesis"]) == 2
    assert any("al menos 2 hipótesis" in msg for msg in m.recibidos)


def test_veredictos_con_otras_palabras_se_entienden(entorno, modo_real):
    g = GUION_CASO3
    modo_real([g[0], g[1], {**g[2], "veredicto": "Descartado"}, g[3], {**g[4], "veredicto": "confirmada"}, g[5]])
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "concluida"
    assert [h["veredicto"] for h in r["hipotesis"]] == ["descartada", "sostenida"]


def test_stream_cortado_por_nightshift_se_reintenta():
    import io
    from agente.modelo import ModeloNightshift, StreamCortado, _juntar_stream
    cortado = io.BytesIO(b'data: {"error": {"message": "failed", "meterless_detail": "provider_deadline"}}\n\n')
    with pytest.raises(StreamCortado, match="provider_deadline"):
        _juntar_stream(cortado)
    with pytest.raises(StreamCortado, match="sin contenido"):
        _juntar_stream(io.BytesIO(b"data: [DONE]\n\n"))
    m = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron", 5, reintentos=1, espera_s=0, stream=True)
    llamadas = []

    def post(cuerpo):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise StreamCortado("Nightshift cortó la respuesta: provider_deadline")
        return {"model": "nvidia/nemotron", "choices": [{"message": {"content": "{}"}}], "usage": {}}

    m._post = post
    assert m.completar([{"role": "user", "content": "hola"}])["texto"] == "{}" and m.reintentos_usados == 1


def test_tres_respuestas_invalidas_seguidas_cortan_la_corrida(entorno, modo_real):
    modo_real(["nada", "", "tampoco", *GUION_CASO3])
    r = orq.correr("¿Por qué?")
    assert r["estado"] == "abstencion" and "3 veces seguidas" in r["abstencion"]["razon"]
    assert r["metricas"]["iteraciones"] == 3


def test_los_errores_que_se_devuelven_al_modelo_quedan_en_la_traza(entorno, modo_real):
    g = GUION_CASO3
    modo_real([g[0], g[1], {**g[2], "hipotesis": "H9"}, *g[2:]])
    r = orq.correr("¿Por qué?")
    devueltos = [e for e in eventos(entorno, r) if e["accion"] == "devolver"]
    assert devueltos and "H9" in devueltos[0]["salida"]


def test_al_repetir_una_grabacion_se_saltan_las_respuestas_vacias():
    from agente.modelo import ModeloGrabado
    m = ModeloGrabado([{"texto": "{\"accion\": \"hipotesis\"}"}, {"texto": ""}, {"texto": "  "}, {"texto": "{\"accion\": \"abstenerse\"}"}])
    assert [m.completar([])["texto"] for _ in range(2)] == ['{"accion": "hipotesis"}', '{"accion": "abstenerse"}']


def test_si_el_modelo_principal_falla_se_intenta_una_vez_el_de_respaldo():
    from agente.modelo import ModeloNightshift, StreamCortado
    m = ModeloNightshift("http://x/v1", "t", "nvidia/nemotron-3-super", 5, reintentos=1, espera_s=0,
                         respaldo="nvidia/nemotron-lightning")
    pedidos = []

    def post(cuerpo):
        pedidos.append(cuerpo["model"])
        if cuerpo["model"] == "nvidia/nemotron-3-super":
            raise StreamCortado("Nightshift cortó la respuesta: provider_deadline")
        return {"model": cuerpo["model"], "choices": [{"message": {"content": "{}"}}], "usage": {}}

    m._post = post
    r = m.completar([{"role": "user", "content": "hola"}])
    assert r["modelo"] == "nvidia/nemotron-lightning" and m.respaldos_usados == 1
    assert pedidos == ["nvidia/nemotron-3-super", "nvidia/nemotron-3-super", "nvidia/nemotron-lightning"]
