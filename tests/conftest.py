import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Modo de muestra, sin credenciales, con logs y salidas en una carpeta temporal."""
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("AGENTE_LOGS", str(tmp_path / "logs"))
    monkeypatch.setenv("AGENTE_SALIDAS", str(tmp_path / "salidas"))
    monkeypatch.setenv("METERLESS_RUNTIME_TOKEN", "")
    return tmp_path


def leer_jsonl(ruta: Path) -> list[dict]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def pregunta(caso: str) -> str:
    return json.loads((RAIZ / "ejemplos" / f"{caso}_entrada.json").read_text(encoding="utf-8"))["pregunta"]
