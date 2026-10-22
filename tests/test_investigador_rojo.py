"""Pruebas EN ROJO del investigador (Paso 10, JPTRS-67): describen lo que el agente debe lograr
con los tres casos plantados y fallan hasta que se programe.

Están marcadas xfail(strict=True): pytest las muestra como "x" mientras fallen y da ERROR en
cuanto empiecen a pasar, para obligar a quitar la marca cuando el investigador funcione.
"""

import pytest

from agente import orquestador as orq
from tests.conftest import pregunta

ROJO = pytest.mark.xfail(strict=True, reason="Paso 10 (JPTRS-67): el investigador todavía no existe")


def _texto(r):
    return " ".join([r.get("conclusion") or "", r.get("recomendacion") or ""] +
                    [h["enunciado"] + " " + h["razon"] for h in r["hipotesis"]]).lower()


@ROJO
def test_caso1_cliente_fiel_con_entrega_firmada_se_pelea(entorno):
    r = orq.correr(pregunta("caso1"))
    assert r["estado"] == "concluida"
    assert "pelear" in _texto(r) and "no pelear" not in (r["conclusion"] or "").lower()
    assert any(h["veredicto"] == "sostenida" for h in r["hipotesis"])


@ROJO
def test_caso2_fraude_real_no_se_pelea(entorno):
    r = orq.correr(pregunta("caso2"))
    assert r["estado"] == "concluida"
    assert "fraude" in _texto(r) and "no pelear" in _texto(r)


@ROJO
def test_caso3_el_pico_es_del_transportista_y_se_descarta_el_fraude(entorno):
    r = orq.correr(pregunta("caso3"))
    assert r["estado"] == "concluida"
    assert "rapidenvio" in _texto(r) and "norte" in _texto(r)
    assert any(h["veredicto"] == "descartada" and "fraude" in h["enunciado"].lower() for h in r["hipotesis"])
