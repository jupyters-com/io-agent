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


# Las disputas del grupo (RapidEnvio · Norte) que trae la cola al preparar: una para pelear sin dudas,
# una para pelear pero con una señal de fraude (la política la rechaza) y una con reclamo previo.
GRUPO = [
    {"disputa_id": "du_A1", "pedido_id": "ORD-1", "cliente_id": "c1", "motivo": "product_not_received",
     "estado": "needs_response", "monto": 61.15, "abierta_en": "2026-09-26 15:00:00", "vence_en": "2026-10-10 23:00:00",
     "transportista": "RapidEnvio", "region": "Norte", "estado_envio": "entregado", "prueba_entrega": "firma",
     "entregado_en": "2026-09-24", "entrega_confirmada": True, "reclamo_previo": False, "pedidos_previos": 3,
     "disputas_previas": 0, "senales_fraude": 0, "vale_pelear": True, "razon_decision": "entrega_confirmada_sin_reclamo"},
    {"disputa_id": "du_B2", "pedido_id": "ORD-2", "cliente_id": "c2", "motivo": "fraudulent",
     "estado": "needs_response", "monto": 41.24, "abierta_en": "2026-09-20 15:00:00", "vence_en": "2026-10-04 23:00:00",
     "transportista": "RapidEnvio", "region": "Norte", "estado_envio": "entregado", "prueba_entrega": "foto",
     "entregado_en": "2026-09-19", "entrega_confirmada": True, "reclamo_previo": False, "pedidos_previos": 0,
     "disputas_previas": 0, "senales_fraude": 1, "vale_pelear": True, "razon_decision": "entrega_confirmada_sin_reclamo"},
    {"disputa_id": "du_C3", "pedido_id": "ORD-3", "cliente_id": "c3", "motivo": "product_not_received",
     "estado": "needs_response", "monto": 130.33, "abierta_en": "2026-09-20 15:00:00", "vence_en": "2026-10-04 23:00:00",
     "transportista": "RapidEnvio", "region": "Norte", "estado_envio": "entregado", "prueba_entrega": "firma",
     "entregado_en": "2026-09-18", "entrega_confirmada": True, "reclamo_previo": True, "pedidos_previos": 1,
     "disputas_previas": 0, "senales_fraude": 0, "vale_pelear": False, "razon_decision": "reclamo_previo"},
]

# Del mismo período pero de otro transportista: vale pelear, aunque no es parte de la causa.
FUERA = [{**GRUPO[0], "disputa_id": "du_D4", "pedido_id": "ORD-4", "transportista": "CargoSur", "region": "Centro",
          "monto": 129.9, "pedidos_previos": 4}]

PICO = {
    # primero lo más específico: MotorFalso responde con la primera clave que aparece en el SQL
    "canonico.mensajes_soporte": [{"pedido_id": "ORD-1", "creado_en": "2026-09-27 10:00:00", "categoria": "consulta",
                                   "texto": "¿Ya está resuelto?"}],
    "FROM canonico.disputas WHERE transportista = 'RapidEnvio' AND region = 'Norte'": GRUPO,
    "FROM canonico.disputas WHERE abierta_en >=": GRUPO + FUERA,
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
