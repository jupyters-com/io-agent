"""El modelo de lenguaje, siempre a través de Meterless Nightshift (proveedor principal).

- ModeloMuestra (SAMPLE_MODE=true): no llama a nada; devuelve texto fijo. Sin credenciales.
- ModeloNightshift: API compatible con OpenAI en METERLESS_BASE_URL, con el contrato de la guía:
  Authorization Bearer, meterless-app y meterless-scope. Tiene tope de tiempo y lleva la cuenta
  de tokens y costo para la alerta de gasto.

El esqueleto todavía no usa el modelo para investigar: eso llega en el Paso 10 (JPTRS-67)
y la integración completa de Meterless en el Paso 13 (JPTRS-68).
"""

import json
import urllib.error
import urllib.request


class ModeloMuestra:
    nombre = "muestra"

    def __init__(self):
        self.tokens, self.costo_usd = 0, 0.0

    def completar(self, mensajes: list[dict]) -> dict:
        return {"texto": "", "modelo": "muestra", "tokens": 0, "costo_usd": 0.0}


class ModeloNightshift:
    nombre = "nightshift"

    def __init__(self, url: str, token: str, modelo: str, timeout_s: float):
        self.url, self.token, self.modelo, self.timeout_s = url, token, modelo, timeout_s
        self.tokens, self.costo_usd = 0, 0.0

    def _post(self, cuerpo: dict) -> dict:  # separado para poder simularlo en las pruebas
        pedido = urllib.request.Request(
            self.url + "/chat/completions", method="POST",
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                     "meterless-app": "io-agent", "meterless-scope": "user"})
        with urllib.request.urlopen(pedido, timeout=self.timeout_s) as r:
            return json.loads(r.read().decode("utf-8"))

    def completar(self, mensajes: list[dict]) -> dict:
        if not self.token:
            raise PermissionError("Falta METERLESS_RUNTIME_TOKEN en .env.local")
        r = self._post({"model": self.modelo, "messages": mensajes})
        uso = r.get("usage") or {}
        tokens = int(uso.get("total_tokens", 0))
        costo = float(uso.get("cost", uso.get("cost_usd", 0.0)) or 0.0)
        self.tokens += tokens
        self.costo_usd += costo
        return {"texto": r["choices"][0]["message"]["content"], "modelo": r.get("model", self.modelo),
                "tokens": tokens, "costo_usd": costo}


def crear(cfg):
    if cfg.modo_muestra:
        return ModeloMuestra()
    return ModeloNightshift(cfg.meterless_url, cfg.meterless_token, cfg.meterless_modelo, cfg.timeout_s)
