"""Diagnóstico: manda a Nightshift el MISMO primer pedido que hace el Investigador y muestra qué pasa.

    python scripts/diagnosticar_modelo.py                    # con la configuración de .env.local
    python scripts/diagnosticar_modelo.py --hola             # solo un "hola": mide la conexión pura
    python scripts/diagnosticar_modelo.py --sin-pensar       # antepone /no_think al prompt de sistema
    python scripts/diagnosticar_modelo.py --extra '{"chat_template_kwargs": {"enable_thinking": false}}'
    python scripts/diagnosticar_modelo.py --stream            # pide la respuesta por partes
    python scripts/diagnosticar_modelo.py --modelo nvidia/nemotron-3.5-super-vl-120b-a12b

Las opciones se pueden combinar. Lo que funcione se deja fijo en .env.local con
AGENTE_SIN_PENSAR=true, METERLESS_STREAM=true y/o METERLESS_EXTRA_BODY=... para que el agente lo use.
"""

import argparse
import json
import sys
import time
import urllib.error
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from agente.config import cargar  # noqa: E402
from agente.investigador import SISTEMA  # noqa: E402
from agente.modelo import ModeloNightshift  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--modelo")
p.add_argument("--hola", action="store_true")
p.add_argument("--sin-pensar", action="store_true")
p.add_argument("--extra", default=None)
p.add_argument("--stream", action="store_true")
a = p.parse_args()

cfg = cargar()
m = ModeloNightshift(cfg.meterless_url, cfg.meterless_token, a.modelo or cfg.meterless_modelo, cfg.timeout_s,
                     reintentos=0, extra=json.loads(a.extra) if a.extra else cfg.meterless_extra,
                     sin_pensar=a.sin_pensar or cfg.sin_pensar, stream=a.stream or cfg.stream)
if a.hola:
    import uuid  # una marca distinta cada vez, para que Nightshift no responda desde su caché
    mensajes = [{"role": "user", "content": f"Reply with one short sentence. (ref {uuid.uuid4().hex[:8]})"}]
else:
    mensajes = [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": "Pregunta: ¿Por qué subieron las disputas en la segunda quincena de septiembre de 2026?"}]
cuerpo = m.cuerpo(mensajes)
print(f"Nightshift: {cfg.meterless_url} · modelo: {m.modelo} · pedido: {'hola' if a.hola else 'primer pedido real'}")
print(f"Stream: {'sí' if m.stream else 'no'} · sin pensar: {'sí' if m.sin_pensar else 'no'} · extra: {json.dumps(m.extra) if m.extra else '-'} · "
      f"token: {'sí' if cfg.meterless_token else 'NO'} · tope: {cfg.timeout_s:g} s\n")
inicio = time.perf_counter()
try:
    datos = m._post(cuerpo)
    print(f"OK en {time.perf_counter() - inicio:.1f} s · respondió {datos.get('model')}")
    print("Uso:", datos.get("usage"))
    print("\nRespuesta (primeros 800 caracteres):\n", (datos["choices"][0]["message"]["content"] or "")[:800])
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code} {e.reason} después de {time.perf_counter() - inicio:.1f} s")
    print("Detalle:", e.read().decode("utf-8", "replace")[:1000])
except Exception as e:
    print(f"Falló después de {time.perf_counter() - inicio:.1f} s: {e}")
