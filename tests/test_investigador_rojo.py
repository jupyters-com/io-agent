"""Pruebas EN ROJO de los tres casos plantados: corren en modo de muestra sobre las corridas reales
grabadas en samples/corridas/ (con Nemotron vía Nightshift y datos de io-engine).

Están marcadas xfail(strict=True): mientras no haya corridas grabadas fallan y pytest las muestra como
"x". Cuando `python scripts/grabar_corridas.py` grabe corridas que resuelven los casos, pasan y pytest
da XPASS(strict) como fallo: eso avisa que hay que QUITAR la marca ROJO, porque ya están en verde.
"""

import re
import unicodedata

import pytest

from agente import orquestador as orq
from tests.conftest import pregunta

ROJO = pytest.mark.xfail(strict=True, reason="Faltan las corridas grabadas (scripts/grabar_corridas.py)")
NO_PELEAR = re.compile(r"\bno (conviene |se debe |hay que |vale la pena |recomendamos )?pelear|aceptar la disputa")


def _plano(texto):
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _texto(r):
    return _plano(" ".join([r["conclusion"] or "", r["recomendacion"] or ""] +
                           [h["enunciado"] + " " + h["razon"] for h in r["hipotesis"]]))


def _miro_la_disputa(r, disputa):
    return any(disputa in e["sql"] for e in r["evidencia"] if e["ok"])


def test_caso1_cliente_fiel_con_entrega_firmada_se_pelea(entorno):
    r = orq.correr(pregunta("caso1"))
    assert r["estado"] == "concluida" and _miro_la_disputa(r, "du_cuKtmopzODI37h")
    recomendacion = _plano(r["recomendacion"])
    assert "pelear" in recomendacion and not NO_PELEAR.search(recomendacion)



def test_caso2_fraude_real_no_se_pelea(entorno):
    r = orq.correr(pregunta("caso2"))
    assert r["estado"] == "concluida" and _miro_la_disputa(r, "du_LRbXAOhoJgujrS")
    assert any(h["veredicto"] == "sostenida" and "fraude" in _plano(h["enunciado"]) for h in r["hipotesis"])
    assert NO_PELEAR.search(_plano(r["recomendacion"]))



def test_caso3_el_pico_es_del_transportista_y_se_descarta_el_fraude(entorno):
    r = orq.correr(pregunta("caso3"))
    assert r["estado"] == "concluida"
    assert "rapidenvio" in _texto(r) and "norte" in _texto(r)
    assert any(h["veredicto"] == "descartada" and "fraude" in _plano(h["enunciado"]) for h in r["hipotesis"])
