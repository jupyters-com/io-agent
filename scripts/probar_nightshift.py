"""Prueba de conexión con Meterless Nightshift (JPTRS-106). No es código del agente.

    python scripts/probar_nightshift.py                 # lista los modelos que expone Nightshift
    python scripts/probar_nightshift.py <modelo>        # manda una pregunta a ese modelo

Lee de .env.local (raíz del repo):
    METERLESS_BASE_URL=http://127.0.0.1:8088/v1        # la URL que muestra la Console
    METERLESS_RUNTIME_TOKEN=...                         # el API key de la Console (NO el de NVIDIA)
    METERLESS_MODEL=meterless/auto                      # opcional; mejor pasar el modelo Nemotron

Sigue el contrato de la guía (sección 4.5): Authorization Bearer, cabeceras meterless-app y
meterless-scope, GET /v1/models y POST /v1/chat/completions. Nunca imprime el token.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENV = RAIZ / ".env.local"
if ENV.is_file():
    for linea in ENV.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BASE = os.getenv("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/")
TOKEN = os.getenv("METERLESS_RUNTIME_TOKEN", "")
CABECERAS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "meterless-app": "io-engine",
    "meterless-scope": "user",
}


def llamar(metodo, ruta, cuerpo=None):
    pedido = urllib.request.Request(
        BASE + ruta, method=metodo, headers=CABECERAS,
        data=json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None,
    )
    try:
        with urllib.request.urlopen(pedido, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"Nightshift respondió HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
    except urllib.error.URLError as e:
        sys.exit(f"No se pudo conectar con Nightshift en {BASE}: {e.reason}. ¿Está abierto?")


print("Nightshift:", BASE)
print("Token cargado:", "sí" if TOKEN else "NO (falta METERLESS_RUNTIME_TOKEN en .env.local)")
if not TOKEN:
    sys.exit(1)

modelos = [m.get("id") for m in llamar("GET", "/models").get("data", [])]
print(f"\nModelos que expone Nightshift ({len(modelos)}):")
for m in modelos:
    print("  ", m, "  <- Nemotron" if "nemotron" in (m or "").lower() else "")

modelo = sys.argv[1] if len(sys.argv) > 1 else os.getenv("METERLESS_MODEL")
if not modelo:
    print("\nElige uno de la lista y vuelve a correr: python scripts/probar_nightshift.py <modelo>")
    sys.exit(0)

print(f"\nPreguntando a: {modelo} ...")
r = llamar("POST", "/chat/completions", {
    "model": modelo,
    "messages": [{"role": "user", "content": "Reply with one sentence confirming this connection works."}],
})
print("Respondió el modelo:", r.get("model"))
print("Respuesta:", r["choices"][0]["message"]["content"].strip())
if "nemotron" not in str(r.get("model", "")).lower():
    print("\nOjo: la respuesta no dice Nemotron. Revisa en Nightshift (detalle de la corrida) qué modelo "
          "la atendió, o pasa el id exacto de un modelo Nemotron.")
