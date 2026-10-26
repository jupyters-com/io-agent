# io-agent · el agente de IO para contracargos

Agente que investiga por qué suben las disputas de pago: propone explicaciones, las prueba con datos y descarta las que la evidencia no sostiene, dejando anotada cada prueba. Si no puede sostener una conclusión con filas, se abstiene.

Construido durante el Open Agent Hackathon 2026 (Track 02 · *The Agent That Can Explain Why*), desde el 22-oct-2026. Todo lo que está en este repo es trabajo nuevo del hackathon.

> **Estado (Paso 9):** el esqueleto corre de punta a punta, cumple el contrato y deja su traza. El investigador llega en el Paso 10; mientras tanto el agente mira el panorama y **se abstiene** en vez de inventar.

## Probarlo (modo de muestra, sin claves ni motor)

```
pip install -r requirements.txt
python run.py ejemplos/caso3_entrada.json
```

O con Docker:

```
docker compose run --rm agente
```

Cada corrida deja:

- `logs/<run_id>.jsonl`: la traza, un evento por línea,
- `logs/cola_aprobacion.jsonl`: el ítem de aprobación (en modo de muestra lo aprueba una regla),
- `salidas/<run_id>.json` y `.md`: la respuesta y el informe legible.

Otras formas de entrada:

```
python run.py '{"pregunta": "¿Por qué subieron las disputas en septiembre?"}'
python run.py --servir          # POST http://localhost:8080/run con {"pregunta": "..."}
```

## De dónde salen los datos

El agente no lee bases ni archivos directamente: le pregunta al motor **io-engine** con la herramienta `consultar(sql)` por MCP. El motor es un **componente previo** (construido antes del 22-oct-2026 00:00 UTC, tag `previo-22oct`) y se levanta aparte.

- **Modo de muestra** (`SAMPLE_MODE=true`, por defecto): usa respuestas reales de io-engine grabadas en `samples/consultas.json` con `scripts/grabar_muestras.py`. No necesita el motor.
- **Modo real** (`SAMPLE_MODE=false`): levanta io-engine (`docker compose up --build` en ese repo), copia `.env.example` como `.env.local` y completa la URL del motor y el token de Nightshift.

## Contrato

La respuesta (con sus filas de evidencia y el informe Markdown), la cola de aprobación y la traza JSONL tienen formato fijo: ver [`CONTRATO.md`](CONTRATO.md) y `contrato/*.schema.json`.

## Ejemplos

`ejemplos/` tiene tres preguntas (los tres casos plantados) con sus salidas, generadas por corridas reales con `python scripts/generar_ejemplos.py`, nunca escritas a mano.

## Pruebas

```
python -m pytest
```

Las pruebas de `tests/test_investigador_rojo.py` están **en rojo a propósito**: describen lo que el investigador del Paso 10 debe lograr con los tres casos y fallan hasta que se programe (aparecen como `x`).

## Topes

| Variable | Por defecto | Qué limita |
| --- | --- | --- |
| `AGENTE_TIMEOUT_S` | `60` | cada llamada externa (motor y modelo), con un reintento si se pasa |
| `AGENTE_MAX_ITERACIONES` | `8` | pasos por corrida |
| `AGENTE_PRESUPUESTO_USD` | `1.0` | gasto en el proveedor del modelo: si se pasa, queda una alerta en la traza |

## Sponsors

- **Meterless:** Nightshift es el proveedor principal de IA del agente (API compatible con OpenAI, con el contrato de Runtime de la guía). Los engines de Meterless se integran en el Paso 13.
- **NVIDIA:** el modelo es Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`), servido a través de Nightshift.
- **Zetaris:** responde `consultar(sql)` en io-engine uniendo las tres fuentes sin copiarlas, con respaldo en DuckDB; cada respuesta registra qué motor respondió.
- **Herramienta de desarrollo:** ver `metadata.json`.

## License

PolyForm Noncommercial 1.0.0 · ver `LICENSE`.
