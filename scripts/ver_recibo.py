"""Descubre cómo entrega Nightshift el recibo firmado de cada respuesta (JPTRS-112). No es código del agente.

    python scripts/ver_recibo.py

Manda una pregunta corta a Nightshift (normal y por stream) e imprime TODO lo que viene fuera del texto:
cabeceras de la respuesta, campos del JSON que no son los de OpenAI y campos de cada parte del stream.
Después prueba algunas rutas donde podría estar el recibo o la llave pública para verificarlo.
Nunca imprime el token. Lee METERLESS_BASE_URL, METERLESS_RUNTIME_TOKEN y METERLESS_MODEL de .env.local.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from agente import recibo as recibos  # noqa: E402
ENV = RAIZ / ".env.local"
if ENV.is_file():
    for linea in ENV.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BASE = os.getenv("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/")
RAIZ_HTTP = BASE[:-3] if BASE.endswith("/v1") else BASE
TOKEN = os.getenv("METERLESS_RUNTIME_TOKEN", "")
MODELO = os.getenv("METERLESS_MODEL", "meterless/auto")
CABECERAS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
             "meterless-app": "io-agent", "meterless-scope": "user"}
ESTANDAR = {"id", "object", "created", "model", "choices", "usage", "system_fingerprint", "service_tier"}


def tapar(texto: str) -> str:
    return texto.replace(TOKEN, "<token>") if TOKEN else texto


def mostrar_cabeceras(h):
    print("  Cabeceras de la respuesta:")
    for k, v in h.items():
        if k.lower() in ("authorization", "set-cookie"):
            v = "<oculto>"
        print(f"    {k}: {tapar(v)[:600]}")


def extras(obj: dict) -> dict:
    fuera = {k: v for k, v in obj.items() if k not in ESTANDAR}
    for i, c in enumerate(obj.get("choices") or []):
        mas = {k: v for k, v in c.items() if k not in ("index", "message", "delta", "finish_reason", "logprobs")}
        if mas:
            fuera[f"choices[{i}]"] = mas
        msg = c.get("message") or c.get("delta") or {}
        mas = {k: v for k, v in msg.items() if k not in ("role", "content", "reasoning_content", "reasoning")}
        if mas:
            fuera[f"choices[{i}].message"] = mas
    if isinstance(obj.get("usage"), dict):
        mas = {k: v for k, v in obj["usage"].items()
               if k not in ("prompt_tokens", "completion_tokens", "total_tokens")}
        if mas:
            fuera["usage (extra)"] = mas
    return fuera


def informar(datos: dict, nombre: str):
    """Guarda el recibo completo en logs/ y dice qué modelo respondió y si la firma verifica."""
    recibo = recibos.buscar(datos)
    if not recibo:
        print("  >>> No vino ningún recibo (campo meterless) en esta respuesta.")
        return
    destino = RAIZ / "logs" / f"recibo_{nombre}.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(tapar(json.dumps(recibo, ensure_ascii=False, indent=2)),
                       encoding="utf-8")
    v = recibos.verificar(recibo)
    print(f"  >>> Recibo {recibo.get('receipt_id')} guardado en logs/{destino.name}")
    print(f"  >>> modelo pedido: {recibo.get('requested_model')} · respondió (según el recibo firmado): "
          f"{recibos.respondio(recibo, v)}")
    print(f"  >>> firma: {v['estado']} · {recibos.TEXTO_FIRMA[v['estado']]}")


def pedir(stream: bool):
    cuerpo = {"model": MODELO, "max_tokens": 400,
              "messages": [{"role": "user", "content": "Responde solo: hola. (prueba de recibo)"}]}
    if stream:
        cuerpo.update(stream=True, stream_options={"include_usage": True})
    print(f"\n=== POST /chat/completions · modelo pedido: {MODELO} · stream={stream}")
    req = urllib.request.Request(BASE + "/chat/completions", method="POST", headers=CABECERAS,
                                 data=json.dumps(cuerpo).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            print(f"  HTTP {r.status}")
            mostrar_cabeceras(r.headers)
            if not stream:
                texto = r.read().decode("utf-8")
                datos = json.loads(texto)
                print("  Modelo que respondió:", datos.get("model"))
                informar(datos, "normal")
                return
            recibo = None
            for linea in r:
                linea = linea.decode("utf-8", "replace").strip()
                if not linea:
                    continue
                if not linea.startswith("data:"):
                    print("  línea del stream (no data):", tapar(linea)[:600])
                    continue
                dato = linea[5:].strip()
                if dato == "[DONE]":
                    print("  [DONE]")
                    informar({"meterless": recibo}, "stream")
                    break
                try:
                    parte = json.loads(dato)
                except json.JSONDecodeError:
                    print("  dato no JSON:", tapar(dato)[:600])
                    continue
                nuevo = recibos.buscar(parte)
                if nuevo:
                    recibo = recibos.juntar(recibo, nuevo)
                mas = extras(parte)
                if mas or parte.get("usage"):
                    print(f"  parte del stream · modelo={parte.get('model')} · campos extra:", ", ".join(mas))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
        mostrar_cabeceras(e.headers)
    except urllib.error.URLError as e:
        sys.exit(f"No se pudo conectar con Nightshift en {BASE}: {e.reason}. ¿Está abierto?")


def probar_rutas():
    print("\n=== Rutas donde podría estar el recibo o la llave para verificarlo")
    for ruta in ("/v1/receipts", "/v1/receipts?limit=1", "/v1/receipts/latest", "/v1/receipts/public-key",
                 "/v1/receipts/verify", "/v1/runtime/receipts", "/v1/keys", "/v1/public-key", "/v1/runtime",
                 "/receipts", "/api/receipts", "/.well-known/meterless", "/.well-known/jwks.json", "/healthz"):
        req = urllib.request.Request(RAIZ_HTTP + ruta, headers=CABECERAS)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f"  {ruta}: HTTP {r.status} · {tapar(r.read().decode('utf-8', 'replace'))[:400]}")
        except urllib.error.HTTPError as e:
            print(f"  {ruta}: HTTP {e.code}")
        except Exception as e:  # noqa: BLE001
            print(f"  {ruta}: {type(e).__name__}")


if not TOKEN:
    sys.exit("Falta METERLESS_RUNTIME_TOKEN en .env.local")
print("Nightshift:", BASE)
pedir(stream=False)
pedir(stream=True)

