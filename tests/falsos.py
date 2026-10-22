"""Un modelo y un motor falsos para probar el ciclo del Investigador sin red."""

import json


class ModeloGuion:
    """Responde, en orden, las acciones de un guion (como lo haría Nemotron)."""
    nombre = "guion"

    def __init__(self, acciones):
        self.acciones = [a if isinstance(a, str) else json.dumps(a, ensure_ascii=False) for a in acciones]
        self.recibidos, self.tokens, self.costo_usd = [], 0, 0.0

    def completar(self, mensajes):
        self.recibidos.append(mensajes[-1]["content"])
        if not self.acciones:
            raise RuntimeError("guion agotado")
        return {"texto": self.acciones.pop(0), "modelo": "nvidia/nemotron-guion", "tokens": 10, "costo_usd": 0.0}


class MotorFalso:
    nombre = "io-engine"

    def __init__(self, respuestas):
        self.respuestas = respuestas  # fragmento del SQL -> filas

    def consultar(self, sql):
        for clave, filas in self.respuestas.items():
            if clave in sql:
                return {"ok": True, "motor": "duckdb", "columnas": list(filas[0]) if filas else [],
                        "filas": filas, "n_filas": len(filas), "truncado": False}
        return {"ok": False, "motor": "duckdb", "filas": [], "n_filas": 0, "error": "Error de SQL: tabla inexistente"}


PICO = {
    "senales_fraude": [{"senales_fraude": 0, "disputas": 13}, {"senales_fraude": 1, "disputas": 3},
                       {"senales_fraude": 2, "disputas": 1}, {"senales_fraude": 4, "disputas": 1}],
    "transportista, region": [{"transportista": "RapidEnvio", "region": "Norte", "disputas": 14,
                               "tarde_o_extraviado": 14, "con_reclamo_previo": 12},
                              {"transportista": "RapidEnvio", "region": "Sur", "disputas": 2,
                               "tarde_o_extraviado": 0, "con_reclamo_previo": 1}],
}

GUION_CASO3 = [
    {"accion": "hipotesis", "hipotesis": [{"id": "H1", "enunciado": "El pico es una ola de fraude"},
                                          {"id": "H2", "enunciado": "Un transportista se atrasó en una región"}]},
    {"accion": "consultar", "hipotesis": "H1",
     "sql": "SELECT senales_fraude, count(*) AS disputas FROM canonico.disputas GROUP BY senales_fraude"},
    {"accion": "veredicto", "hipotesis": "H1", "veredicto": "descartada",
     "razon": "De 18 disputas, solo 2 tienen 2 o más señales de fraude", "evidencia": ["E1"]},
    {"accion": "consultar", "hipotesis": "H2",
     "sql": "SELECT transportista, region, razon_decision, count(*) AS disputas FROM canonico.disputas "
            "GROUP BY transportista, region, razon_decision"},
    {"accion": "veredicto", "hipotesis": "H2", "veredicto": "sostenida",
     "razon": "14 de 18 son de RapidEnvio en el Norte, todas tarde o extraviadas", "evidencia": ["E2"]},
    {"accion": "concluir", "conclusion": "El pico no es fraude: lo explica RapidEnvio en el Norte (14 de 18).",
     "recomendacion": "Reclamar a RapidEnvio y resolver con los clientes que reclamaron antes."},
]
