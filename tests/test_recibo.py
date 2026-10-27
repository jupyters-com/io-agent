"""El recibo firmado de Nightshift: se saca de la respuesta, se verifica con la llave fijada y va a la traza."""

import base64
import copy
import json
from pathlib import Path

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402

from agente import recibo as recibos  # noqa: E402
from agente.modelo import _juntar_stream  # noqa: E402

REAL = json.loads((Path(__file__).parent / "datos" / "recibo_nightshift.json").read_text(encoding="utf-8"))
LIGHTNING = "nvidia/nemotron-3.5-lightning-30b-a3b"
SUPER = "nvidia/nemotron-3.5-super-vl-120b-a12b"


def test_recibo_real_de_nightshift_verifica(monkeypatch):
    # un recibo real (prueba "hola", 26-oct), firmado por meterlessd de esta instalación
    monkeypatch.delenv("METERLESS_RECIBO_PUBKEY", raising=False)
    v = recibos.verificar(REAL)
    assert v["estado"] == "verificada" and v["firmante"] == "meterlessd"
    assert recibos.respondio(REAL, v) == LIGHTNING


def test_recibo_real_alterado_no_verifica(monkeypatch):
    monkeypatch.delenv("METERLESS_RECIBO_PUBKEY", raising=False)
    r = copy.deepcopy(REAL)
    r["receipt_envelope"]["body"]["receipt"]["winning_route"]["model"] = SUPER
    assert recibos.verificar(r)["estado"] == "no_verificada"


def test_sobre_de_otro_recibo_no_cuenta(monkeypatch):
    monkeypatch.delenv("METERLESS_RECIBO_PUBKEY", raising=False)
    r = copy.deepcopy(REAL)
    r["receipt_id"] = "rcpt_otro"
    assert recibos.verificar(r)["estado"] == "no_coincide"


@pytest.fixture
def llave(monkeypatch):
    privada = Ed25519PrivateKey.generate()
    publica = base64.b64encode(privada.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    monkeypatch.setenv("METERLESS_RECIBO_PUBKEY", publica)
    return privada, publica


def firmado(privada, publica, routed=SUPER):
    cuerpo = {"receipt": {"receipt_id": "rcpt_prueba", "winning_route": {"model": routed}},
              "signer": "meterlessd", "ts_ms": 1}
    return {"receipt_id": "rcpt_prueba", "requested_model": SUPER, "routed_model": routed,
            "receipt_envelope": {"body": cuerpo, "pubkey_b64": publica,
                                 "sig_b64": base64.b64encode(privada.sign(recibos.canonico(cuerpo))).decode()}}


def test_otra_llave_no_cuenta(llave):
    otra = Ed25519PrivateKey.generate()
    publica = base64.b64encode(otra.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    assert recibos.verificar(firmado(otra, publica))["estado"] == "otra_llave"


def test_sin_recibo_y_sin_firma():
    assert recibos.verificar(None)["estado"] == "sin_recibo"
    assert recibos.verificar({"receipt_id": "x"})["estado"] == "sin_firma"


def test_resumen_avisa_si_respondio_otro_modelo(llave):
    r = firmado(*llave, routed=LIGHTNING)
    entrada, salida, bien = recibos.resumen({"recibo": r, "firma": recibos.verificar(r)}, SUPER)
    assert entrada == "pedido: nemotron-3.5-super-vl-120b-a12b"
    assert "respondió: nemotron-3.5-lightning-30b-a3b" in salida and "rcpt_prueba" in salida
    assert bien is False  # la firma es buena, pero respondió otro modelo: alerta en la traza


def test_resumen_todo_bien(llave):
    r = firmado(*llave)
    _, salida, bien = recibos.resumen({"recibo": r, "firma": recibos.verificar(r)}, SUPER)
    assert bien and "firma Ed25519 de meterlessd verificada" in salida


def test_stream_junta_el_recibo(llave):
    r = firmado(*llave)
    partes = [{"model": "m", "choices": [{"delta": {"content": "hola"}}],
               "meterless": {"receipt_id": "rcpt_prueba"}},
              {"model": "m", "choices": [{"delta": {}, "finish_reason": "stop"}], "meterless": r}]
    lineas = [f"data: {json.dumps(p)}".encode() for p in partes] + [b"data: [DONE]"]
    junto = _juntar_stream(lineas)
    assert recibos.verificar(junto["meterless"])["estado"] == "verificada"
