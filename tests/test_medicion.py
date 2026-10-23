"""[Challenge] JPTRS-77/78: el set de prueba y cómo se puntúa al agente con y sin la capa."""

from agente import medicion

FILAS = [
    {"disputa_id": "du_B", "vale_pelear": False, "razon_decision": "reclamo_previo", "causa_operativa": True,
     "transportista": "RapidEnvio", "region": "Norte", "motivo": "fraudulent", "estado": "needs_response", "monto": 1},
    {"disputa_id": "du_A", "vale_pelear": True, "razon_decision": "entrega_confirmada_sin_reclamo",
     "causa_operativa": False, "motivo": "unrecognized", "estado": "needs_response", "monto": 2},
    {"disputa_id": "du_C", "vale_pelear": False, "razon_decision": "sospecha_de_fraude", "causa_operativa": False,
     "motivo": "fraudulent", "estado": "needs_response", "monto": 3},
]


def test_la_respuesta_esperada_sale_de_la_definicion_canonica():
    s = {f["disputa_id"]: f for f in medicion.filas_del_set(FILAS)}
    assert list(s) == ["du_A", "du_B", "du_C"]
    assert s["du_A"]["esperada"] == "vale la pena pelear"
    assert s["du_B"]["esperada"] == "causa operativa" and "RapidEnvio" in s["du_B"]["razon"]
    assert s["du_C"]["esperada"] == "no vale la pena" and s["du_C"]["caso_limite"]


def test_la_conclusion_del_agente_se_clasifica():
    def r(texto, estado="concluida"):
        return {"estado": estado, "conclusion": texto}
    assert medicion.clasificar(r("Sí, vale la pena pelear la disputa du_A, por 129.9 dólares.")) == "pelear"
    assert medicion.clasificar(r("No vale la pena pelear la disputa du_A: no existe prueba de entrega.")) == "no_pelear"
    assert medicion.clasificar(r("No, no vale la pena pelear esta disputa. Hay 4 señales de fraude.")) == "no_pelear"
    assert medicion.clasificar(r("Conviene pelearla: el pedido llegó con firma.")) == "pelear"
    assert medicion.clasificar(r(None, "abstencion")) == "abstencion"
    assert medicion.clasificar(r("El pedido llegó.")) == "sin_clasificar"


def test_se_cuentan_aciertos_defensas_y_abstenciones():
    pelear = {"esperada": "vale la pena pelear"}
    no = {"esperada": "causa operativa"}
    si_dice = {"estado": "concluida", "conclusion": "Sí, vale la pena pelear la disputa."}
    no_dice = {"estado": "concluida", "conclusion": "No vale la pena pelear la disputa."}
    abst = {"estado": "abstencion", "conclusion": None, "abstencion": {"razon": "no alcanza"}}
    filas = [medicion.puntuar(pelear, si_dice), medicion.puntuar(no, si_dice), medicion.puntuar(pelear, no_dice),
             medicion.puntuar(no, abst), medicion.puntuar(no, None)]
    assert [f["resultado"] for f in filas] == ["acierto", "defensa que no debía armarse", "defensa perdida",
                                               "abstención", "pendiente"]
    res = medicion.resumen(filas)
    assert res["medidos"] == 4 and res["acierto"] == 1 and res["tasa_acierto"] == 25.0


def test_decir_que_no_hubo_entrega_cuando_si_la_hubo_es_un_acierto_con_razon_falsa():
    caso = {"esperada": "causa operativa", "entrega_confirmada": "True"}
    falsa = {"estado": "concluida", "conclusion": "No vale la pena pelear la disputa. No existe prueba de entrega."}
    buena = {"estado": "concluida", "conclusion": "No, no vale la pena pelearla: el cliente reclamó antes."}
    assert medicion.puntuar(caso, falsa)["resultado"] == "acierto con una razón falsa"
    assert medicion.puntuar(caso, buena)["resultado"] == "acierto"
    sin_entrega = {"esperada": "causa operativa", "entrega_confirmada": "False"}
    assert medicion.puntuar(sin_entrega, falsa)["resultado"] == "acierto"
    res = medicion.resumen([medicion.puntuar(caso, falsa), medicion.puntuar(caso, buena)])
    assert res["tasa_acierto"] == 50.0 and res["tasa_decision"] == 100.0


def test_no_se_puede_pelear_es_no_pelear():
    r = {"estado": "concluida", "conclusion": "No se puede pelear la disputa du_X porque no hay evidencia de entrega."}
    assert medicion.clasificar(r) == "no_pelear"
