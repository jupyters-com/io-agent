"""Cola de aprobación: ninguna respuesta sale sin pasar por aquí.

Es una cola lógica (logs/cola_aprobacion.jsonl), sin pausas humanas mientras el agente corre:
- SAMPLE_MODE=true: la regla "auto_muestra" aprueba y queda registrado quién y por qué.
- Modo real: el ítem queda "pendiente" hasta que una persona lo decida (Paso 11, JPTRS-60).
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ColaAprobacion:
    def __init__(self, carpeta: Path):
        self.ruta = Path(carpeta) / "cola_aprobacion.jsonl"
        self.ruta.parent.mkdir(parents=True, exist_ok=True)

    def encolar(self, run_id: str, resumen: str, modo_muestra: bool) -> dict:
        item = {"item_id": f"AP-{run_id}", "run_id": run_id, "tipo": "respuesta",
                "estado": "pendiente", "creado_en": _ahora(), "decidido_en": None,
                "decidido_por": None, "motivo": None, "resumen": resumen[:300]}
        if modo_muestra:
            item.update(estado="aprobada", decidido_en=_ahora(), decidido_por="regla:auto_muestra",
                        motivo="SAMPLE_MODE=true: en modo de muestra una regla aprueba sin intervención humana.")
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def leer(self) -> list[dict]:
        if not self.ruta.exists():
            return []
        return [json.loads(l) for l in self.ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
