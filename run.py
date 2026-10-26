"""Entrada del agente: una pregunta en JSON entra, una respuesta en JSON sale.

    python run.py '{"pregunta": "¿Por qué subieron las disputas en septiembre?"}'
    python run.py ejemplos/caso3_entrada.json
    echo {"pregunta": "..."} | python run.py -
    python run.py --servir            # POST /run en http://localhost:8080/run

Con SAMPLE_MODE=true (por defecto) corre sin credenciales y sin el motor.
Deja la traza en logs/<run_id>.jsonl y la respuesta + informe en salidas/<run_id>.json y .md.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agente.orquestador import correr


def leer_entrada(arg: str) -> dict:
    if arg == "-":
        texto = sys.stdin.read()
    elif Path(arg).is_file():
        texto = Path(arg).read_text(encoding="utf-8")
    else:
        texto = arg
    entrada = json.loads(texto)
    if not isinstance(entrada, dict) or not str(entrada.get("pregunta", "")).strip():
        raise ValueError('La entrada debe ser un JSON con "pregunta".')
    return entrada


class Manejador(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/run":
            return self._responder(404, {"error": "Usa POST /run"})
        try:
            largo = int(self.headers.get("Content-Length", 0))
            entrada = leer_entrada(self.rfile.read(largo).decode("utf-8"))
            self._responder(200, correr(entrada["pregunta"]))
        except (ValueError, json.JSONDecodeError) as e:
            self._responder(400, {"error": str(e)})

    def _responder(self, codigo, cuerpo):
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)


def main(argv):
    if argv[:1] == ["--servir"]:
        puerto = int(os.getenv("AGENTE_PUERTO", "8080"))
        print(f"Agente escuchando en http://0.0.0.0:{puerto}/run", flush=True)
        ThreadingHTTPServer(("0.0.0.0", puerto), Manejador).serve_forever()
        return 0
    if not argv:
        print(__doc__)
        return 2
    respuesta = correr(leer_entrada(argv[0])["pregunta"])
    print(json.dumps(respuesta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
