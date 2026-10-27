"""El modelo de lenguaje, siempre a través de Meterless Nightshift (proveedor principal).

- ModeloNightshift (SAMPLE_MODE=false): API compatible con OpenAI en METERLESS_BASE_URL, con el
  contrato de la guía (Authorization Bearer, meterless-app, meterless-scope). Tope de tiempo por
  llamada y cuenta de tokens y costo para la alerta de gasto.
- ModeloGrabado (SAMPLE_MODE=true): repite, en orden, las respuestas que Nemotron dio en una
  corrida real grabada (samples/corridas/). Nunca respuestas escritas a mano.
- Grabadora: envuelve al modelo real y guarda lo que responde, para crear esas grabaciones.
"""

import json
import os
import time
import urllib.error
import urllib.request

from agente import recibo as recibos

REINTENTAR = (429, 500, 502, 503, 504)


class StreamCortado(RuntimeError):
    """Nightshift cerró el stream con un error o sin mandar respuesta (p. ej. provider_deadline)."""


def _juntar_stream(respuesta) -> dict:
    """Arma una respuesta normal a partir de un stream SSE (líneas "data: {...}")."""
    texto, modelo, uso, termino = [], None, {}, False
    recibo = None
    for linea in respuesta:
        linea = linea.decode("utf-8", "replace").strip()
        if not linea.startswith("data:"):
            continue
        dato = linea[5:].strip()
        if dato == "[DONE]":
            termino = True
            break
        parte = json.loads(dato)
        nuevo = recibos.buscar(parte)
        if nuevo:
            recibo = recibos.juntar(recibo, nuevo)
        if parte.get("error"):
            error = parte["error"]
            detalle = error.get("meterless_detail") or error.get("message") if isinstance(error, dict) else error
            raise StreamCortado(f"Nightshift cortó la respuesta: {detalle}")
        modelo = parte.get("model", modelo)
        uso = parte.get("usage") or uso
        for opcion in parte.get("choices", []):
            texto.append((opcion.get("delta") or {}).get("content") or "")
            termino = termino or bool(opcion.get("finish_reason"))
    if not "".join(texto).strip():
        raise StreamCortado("Nightshift cerró la respuesta sin contenido"
                            + ("" if termino else " (se cortó antes de terminar, posible provider_deadline)"))
    return {"model": modelo, "choices": [{"message": {"content": "".join(texto)}}], "usage": uso,
            "meterless": recibo}


class SinMasRespuestas(RuntimeError):
    """El modelo grabado ya no tiene respuestas para esta corrida."""


class ModeloNightshift:
    nombre = "nightshift"

    def __init__(self, url: str, token: str, modelo: str, timeout_s: float, reintentos: int = 2,
                 espera_s: float = 5.0, extra: dict | None = None, sin_pensar: bool = False,
                 stream: bool = False, respaldo: str = "", app: str = "io-agent"):
        self.url, self.token, self.modelo, self.timeout_s = url, token, modelo, timeout_s
        self.app = app
        self.respaldo, self.respaldos_usados = respaldo, 0
        self.extra, self.sin_pensar, self.stream = dict(extra or {}), sin_pensar, stream
        self.reintentos, self.espera_s = reintentos, espera_s
        self.tokens, self.costo_usd = 0, 0.0
        self.reintentos_usados = 0
        self.ultimo_recibo = None  # el recibo de la última llamada, con su firma ya verificada

    def _post(self, cuerpo: dict) -> dict:  # separado para poder simularlo en las pruebas
        pedido = urllib.request.Request(
            self.url + "/chat/completions", method="POST",
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                     "meterless-app": self.app, "meterless-scope": "user"})
        with urllib.request.urlopen(pedido, timeout=self.timeout_s) as r:
            if not cuerpo.get("stream"):
                return json.loads(r.read().decode("utf-8"))
            return _juntar_stream(r)

    def cuerpo(self, mensajes: list[dict], modelo: str | None = None) -> dict:
        if self.sin_pensar:
            if mensajes and mensajes[0]["role"] == "system":
                mensajes = [{"role": "system", "content": "/no_think\n" + mensajes[0]["content"]}, *mensajes[1:]]
            else:
                mensajes = [{"role": "system", "content": "/no_think"}, *mensajes]
        cuerpo = {"model": modelo or self.modelo, "messages": mensajes, **self.extra}
        if self.stream:
            cuerpo.update(stream=True, stream_options={"include_usage": True})
        return cuerpo

    def completar(self, mensajes: list[dict]) -> dict:
        """Pide al modelo principal; si falla tras sus reintentos y hay modelo de respaldo, lo intenta una vez."""
        if not self.token:
            raise PermissionError("Falta METERLESS_RUNTIME_TOKEN en .env.local")
        try:
            return self._completar_con(mensajes, self.modelo, self.reintentos)
        except RuntimeError as e:
            if not self.respaldo or self.respaldo == self.modelo:
                raise
            self.respaldos_usados += 1
            try:
                return self._completar_con(mensajes, self.respaldo, 1)
            except RuntimeError as e2:
                raise RuntimeError(f"{e} · y el respaldo {self.respaldo} también falló: {e2}") from e2

    def _completar_con(self, mensajes: list[dict], modelo: str, reintentos: int) -> dict:
        intento = 0
        while True:
            try:
                r = self._post(self.cuerpo(mensajes, modelo))
                break
            except urllib.error.HTTPError as e:
                detalle = e.read().decode("utf-8", "replace")[:300] if e.fp else ""
                if e.code in REINTENTAR and intento < reintentos:
                    intento += 1
                    self.reintentos_usados += 1
                    time.sleep(self.espera_s * intento)
                    continue
                raise RuntimeError(f"Nightshift respondió HTTP {e.code} {e.reason}"
                                   + (f": {detalle}" if detalle else "")) from e
            except StreamCortado as e:
                if intento < reintentos:
                    intento += 1
                    self.reintentos_usados += 1
                    time.sleep(self.espera_s * intento)
                    continue
                raise RuntimeError(f"{e} (tras {intento} reintento(s))") from e
            except (TimeoutError, urllib.error.URLError) as e:
                es_tiempo = isinstance(e, TimeoutError) or "timed out" in str(e)
                if es_tiempo and intento < reintentos:
                    intento += 1
                    self.reintentos_usados += 1
                    time.sleep(self.espera_s * intento)
                    continue
                if es_tiempo:
                    raise RuntimeError(f"Nightshift no respondió dentro de {self.timeout_s:g} s "
                                       f"(AGENTE_TIMEOUT_S), tras {intento} reintento(s)") from e
                raise
        uso = r.get("usage") or {}
        tokens = int(uso.get("total_tokens", 0))
        costo = float(uso.get("cost", uso.get("cost_usd", 0.0)) or 0.0)
        self.tokens += tokens
        self.costo_usd += costo
        recibo = recibos.buscar(r)
        info = {"modelo": r.get("model", modelo), "pedido": modelo, "recibo": recibo,
                "firma": recibos.verificar(recibo)}
        self.ultimo_recibo = info
        return {"texto": r["choices"][0]["message"]["content"] or "", "modelo": r.get("model", modelo),
                "tokens": tokens, "costo_usd": costo, "recibo": info}


class ModeloGrabado:
    nombre = "grabado"

    def __init__(self, turnos: list[dict], modelo: str = "grabado"):
        # Las respuestas vacías de grabaciones viejas eran cortes de Nightshift (provider_deadline);
        # hoy esos cortes se reintentan y no cuentan como vuelta, así que al repetir se saltan.
        turnos = [t for t in turnos if str(t.get("texto", "")).strip()]
        self.turnos, self.modelo, self.i = turnos, modelo, 0
        self.tokens, self.costo_usd = 0, 0.0

    def completar(self, mensajes: list[dict]) -> dict:
        if self.i >= len(self.turnos):
            raise SinMasRespuestas("No hay una corrida grabada (o se terminó) para esta pregunta en modo de muestra. Para preguntas nuevas usa el modo real / For new questions use live mode: SAMPLE_MODE=false (README.md, «Live mode: new questions»; README.es.md, «Modo real: preguntas nuevas»).")
        t = self.turnos[self.i]
        self.i += 1
        info = t.get("recibo")
        if info:  # la firma del recibo grabado se vuelve a verificar al repetir, no se confía en lo anotado
            info = {**info, "firma": recibos.verificar(info.get("recibo")), "grabado": True}
        r = {"texto": t["texto"], "modelo": t.get("modelo", self.modelo), "tokens": 0, "costo_usd": 0.0}
        if info:  # las grabaciones anteriores a JPTRS-112 no guardaban el recibo
            r["recibo"] = info
        return r


class Grabadora:
    def __init__(self, modelo):
        self.modelo, self.turnos = modelo, []
        self.nombre = modelo.nombre

    @property
    def tokens(self):
        return self.modelo.tokens

    @property
    def costo_usd(self):
        return self.modelo.costo_usd

    def completar(self, mensajes):
        r = self.modelo.completar(mensajes)
        turno = {"texto": r["texto"], "modelo": r["modelo"]}
        if r.get("recibo"):
            turno["recibo"] = r["recibo"]
        self.turnos.append(turno)
        return r


def crear(cfg, turnos=None):
    if cfg.modo_muestra:
        return ModeloGrabado(turnos or [])
    return ModeloNightshift(cfg.meterless_url, cfg.meterless_token, cfg.meterless_modelo, cfg.timeout_s,
                            extra=cfg.meterless_extra, sin_pensar=cfg.sin_pensar, stream=cfg.stream,
                            reintentos=cfg.reintentos_modelo, espera_s=10.0, respaldo=cfg.modelo_respaldo,
                            # Sin la capa, otra app en Nightshift: lo que Nightshift recuerde de las corridas con la
                            # capa (esquema canónico, conclusiones) no se cuela en la comparación.
                            app=os.getenv("METERLESS_APP") or
                                ("io-agent" if getattr(cfg, "capa_semantica", True) else "io-agent-sin-capa"))
