# io-agent · el agente de IO para contracargos

Agente que investiga por qué suben las disputas de pago: propone explicaciones, las prueba con datos y descarta las que la evidencia no sostiene, dejando anotada cada prueba. Si no puede sostener una conclusión con filas, se abstiene.

Construido durante el Open Agent Hackathon 2026 (Track 02 · *The Agent That Can Explain Why*), desde el 22-oct-2026. Todo lo que está en este repo es trabajo nuevo del hackathon.

## Cómo investiga

El **Investigador** conversa con el modelo (Nemotron, vía Meterless Nightshift). En cada vuelta el modelo responde una acción en JSON y nuestro código la ejecuta y la anota:

1. **Propone hipótesis** (H1, H2…), incluida la explicación más obvia aunque sea falsa (por ejemplo, "es fraude").
2. **Las prueba** con `consultar(sql)` contra io-engine. Cada resultado queda como evidencia E1, E2…
3. **Da un veredicto** (sostenida o descartada) citando la evidencia. El **Evaluador** lo revisa y lo devuelve si la evidencia no existe, falló o no trae filas.
4. **Concluye** solo si el Evaluador acepta: todas las hipótesis con veredicto y al menos una sostenida. Si los datos no alcanzan, **se abstiene**.

La IA piensa; el código hace y registra. Topes: `AGENTE_MAX_ITERACIONES` vueltas y `AGENTE_TIMEOUT_S` por llamada.

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
- `logs/<run_id>.evidencia.jsonl`: cada consulta con sus filas y la hipótesis que probaba,
- `logs/cola_aprobacion.jsonl`: el ítem de aprobación (en modo de muestra lo aprueba una regla),
- `salidas/<run_id>.json` y `.md`: la respuesta y el informe legible.

Otras formas de entrada:

```
python run.py '{"pregunta": "¿Por qué subieron las disputas en septiembre?"}'
python run.py --servir          # POST http://localhost:8080/run con {"pregunta": "..."}
```

## De dónde salen los datos

El agente no lee bases ni archivos directamente: le pregunta al motor **io-engine** con la herramienta `consultar(sql)` por MCP. El motor es un **componente previo** (construido antes del 22-oct-2026 00:00 UTC, tag `previo-22oct`) y se levanta aparte.

- **Modo de muestra** (`SAMPLE_MODE=true`, por defecto): repite **corridas reales grabadas** en `samples/corridas/`: lo que respondió Nemotron y las filas que devolvió io-engine, tal cual. No necesita el motor, ni Nightshift, ni claves. Una pregunta sin corrida grabada termina en abstención.
- **Modo real** (`SAMPLE_MODE=false`): levanta io-engine (`docker compose up --build` en ese repo), abre Nightshift con un lane Nemotron, copia `.env.example` como `.env.local` y completa la URL del motor y el token de Nightshift.
- **Grabar corridas**: con todo lo del modo real levantado, `python scripts/grabar_corridas.py` corre los tres ejemplos, los graba en `samples/corridas/` y regenera `ejemplos/`.

## Contrato

La respuesta (con sus filas de evidencia y el informe Markdown), la cola de aprobación y la traza JSONL tienen formato fijo: ver [`CONTRATO.md`](CONTRATO.md) y `contrato/*.schema.json`.

## Ejemplos

`ejemplos/` tiene tres preguntas (los tres casos plantados) con sus salidas, generadas por corridas reales con `python scripts/generar_ejemplos.py`, nunca escritas a mano.

## Pruebas

```
python -m pytest
```

`tests/test_investigador.py` prueba el ciclo completo con un modelo de guion (sin red). Las de `tests/test_investigador_rojo.py` están **en rojo** hasta que existan las corridas grabadas de los tres casos (aparecen como `x`). Cuando pasen, pytest avisa con `XPASS(strict)` y hay que quitarles la marca.

## Topes

| Variable | Por defecto | Qué limita |
| --- | --- | --- |
| `AGENTE_TIMEOUT_S` | `60` | cada llamada externa (motor y modelo), con un reintento si se pasa |
| `AGENTE_MAX_ITERACIONES` | `16` | vueltas con el modelo por corrida |
| `AGENTE_PRESUPUESTO_USD` | `1.0` | gasto en el proveedor del modelo: si se pasa, queda una alerta en la traza |

## Sponsors

- **Meterless:** Nightshift es el proveedor principal de IA del agente (API compatible con OpenAI, con el contrato de Runtime de la guía). Los engines de Meterless se integran en el Paso 13.
- **NVIDIA:** el modelo es Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`), servido a través de Nightshift.
- **Zetaris:** responde `consultar(sql)` en io-engine uniendo las tres fuentes sin copiarlas, con respaldo en DuckDB; cada respuesta registra qué motor respondió.
- **Herramienta de desarrollo:** ver `metadata.json`.

## License

PolyForm Noncommercial 1.0.0 · ver `LICENSE`.
