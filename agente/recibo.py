"""El recibo firmado que Nightshift adjunta a cada respuesta (JPTRS-112).

Cada respuesta de Nightshift trae un objeto `meterless` (esquema meterless.compute_receipt.v1) con el modelo
pedido (`requested_model`), el que respondió (`routed_model`), el id del recibo y un sobre firmado
(`receipt_envelope`):

    receipt_envelope = {"body": {"receipt": {...}, "signer": "meterlessd", "ts_ms": …, "manifest_hash": …,
                                 "llama_cpp_ref": …},
                        "pubkey_b64": "…", "sig_b64": "…"}

La firma es Ed25519 sobre el JSON canónico de `body` (claves ordenadas, sin espacios, UTF-8). Acá se verifica en
el momento de la llamada, con la llave fijada (METERLESS_RECIBO_PUBKEY, por defecto la de meterlessd de esta
instalación): una firma hecha con otra llave no cuenta, aunque el sobre traiga esa otra llave adentro. El modelo
que respondió se toma del recibo firmado, no del campo suelto de la respuesta.
"""

import base64
import json
import os

LLAVE_METERLESSD = "TpDAhneukUt5kl5UMJWpZGZDdbOZ0Lxt59+Ua4WQ/N0="


def llave_fijada() -> str:
    return os.getenv("METERLESS_RECIBO_PUBKEY", LLAVE_METERLESSD).strip()


def buscar(obj) -> dict | None:
    """El recibo dentro de una respuesta (o de una parte del stream), esté donde esté."""
    if isinstance(obj, dict):
        m = obj.get("meterless")
        if isinstance(m, dict) and (m.get("receipt_id") or m.get("receipt_envelope") or m.get("routed_model")):
            return m
        for v in obj.values():
            if isinstance(v, (dict, list)):
                r = buscar(v)
                if r:
                    return r
    elif isinstance(obj, list):
        for v in obj:
            r = buscar(v)
            if r:
                return r
    return None


def juntar(previo: dict | None, nuevo: dict | None) -> dict | None:
    """En el stream el recibo puede llegar por partes: se van sumando los campos."""
    if not nuevo:
        return previo
    return {**(previo or {}), **nuevo}


def canonico(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verificar(recibo: dict | None) -> dict:
    """{"estado": verificada | no_verificada | sin_firma | otra_llave | no_coincide | sin_libreria | sin_recibo,
        "firmado": el recibo que está dentro de la firma (o None)}"""
    if not recibo:
        return {"estado": "sin_recibo", "firmado": None}
    sobre = recibo.get("receipt_envelope") or {}
    cuerpo = sobre.get("body")
    if not (isinstance(cuerpo, dict) and sobre.get("sig_b64")):
        return {"estado": "sin_firma", "firmado": None}
    if sobre.get("pubkey_b64") and sobre["pubkey_b64"] != llave_fijada():
        return {"estado": "otra_llave", "firmado": None}
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return {"estado": "sin_libreria", "firmado": None}
    llave = Ed25519PublicKey.from_public_bytes(base64.b64decode(llave_fijada()))
    try:
        llave.verify(base64.b64decode(sobre["sig_b64"]), canonico(cuerpo))
    except (InvalidSignature, ValueError):
        return {"estado": "no_verificada", "firmado": None}
    firmado = cuerpo.get("receipt") or {}
    # el sobre tiene que ser el de esta respuesta, no uno copiado de otra
    if recibo.get("receipt_id") and firmado.get("receipt_id") != recibo["receipt_id"]:
        return {"estado": "no_coincide", "firmado": firmado}
    return {"estado": "verificada", "firmado": firmado, "firmante": cuerpo.get("signer"), "ts_ms": cuerpo.get("ts_ms")}


def _corto(modelo) -> str:
    return str(modelo or "?").split("/")[-1]


TEXTO_FIRMA = {"verificada": "firma Ed25519 de meterlessd verificada",
               "no_verificada": "firma inválida",
               "sin_firma": "sin firma en la respuesta",
               "otra_llave": "firmado con otra llave: no cuenta",
               "no_coincide": "la firma es de otro recibo",
               "sin_libreria": "firma sin verificar (falta la librería cryptography)",
               "sin_recibo": "Nightshift no mandó recibo"}


def respondio(recibo: dict | None, firma: dict | None = None) -> str | None:
    """El modelo que respondió: el del recibo firmado si verificó; si no, el que dice la respuesta."""
    for r in ((firma or {}).get("firmado"), recibo):
        if r:
            m = r.get("routed_model") or (r.get("winning_route") or {}).get("model") or (r.get("routing") or {}).get("winner")
            if m:
                return m
    return None


def resumen(info: dict | None, pedido: str) -> tuple[str, str, bool]:
    """(entrada, salida, todo_bien) para la línea de la traza."""
    info = info or {}
    r = info.get("recibo") or {}
    v = info.get("firma") or {"estado": "sin_recibo"}
    pedido_m = r.get("requested_model") or pedido
    modelo = respondio(r, v) or info.get("modelo")
    entrada = f"pedido: {_corto(pedido_m)}"
    salida = f"respondió: {_corto(modelo)} · {r.get('receipt_id') or 'sin id'} · {TEXTO_FIRMA[v['estado']]}"
    bien = v["estado"] == "verificada" and _corto(pedido_m) == _corto(modelo)
    return entrada, salida, bien
