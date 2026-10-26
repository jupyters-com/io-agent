# io-agent · el agente de IO para contracargos

Agente que investiga por qué suben las disputas de pago: propone explicaciones, las prueba con datos y descarta las que la evidencia no sostiene, dejando anotada cada prueba. Si no puede sostener una conclusión con filas, se abstiene.

Construido durante el Open Agent Hackathon 2026 (Track 02 · *The Agent That Can Explain Why*), desde el 22-oct-2026. Todo lo que está en este repo es trabajo nuevo del hackathon.

## Cómo investiga

El **Investigador** conversa con el modelo (Nemotron, vía Meterless Nightshift). En cada vuelta el modelo responde una acción en JSON y nuestro código la ejecuta y la anota:

1. **Propone hipótesis** (H1, H2…), incluida la explicación más obvia aunque sea falsa (por ejemplo, "es fraude").
2. **Las prueba** con `consultar(sql)` contra io-engine. Cada resultado queda como evidencia E1, E2…
3. **Da un veredicto** (sostenida o descartada) citando la evidencia. El **Evaluador** lo revisa y lo devuelve si la evidencia no existe, falló o no trae filas.
4. **Concluye** solo si el Evaluador acepta: todas las hipótesis con veredicto y al menos una sostenida. Si los datos no alcanzan, **se abstiene**.

Todo lo que sale en el informe (enunciados, razones, conclusión y recomendación) lo lee la dueña de la tienda, así que el Evaluador también devuelve lo que trae términos técnicos (`product_not_received`, `zona_con_atrasos=true`). Si devuelve la misma cosa más de `AGENTE_TOPE_DEVOLUCIONES` veces, el agente se abstiene.

La IA piensa; el código hace y registra. Topes: `AGENTE_MAX_ITERACIONES` vueltas y `AGENTE_TIMEOUT_S` por llamada.

## Después de investigar: la cola de aprobación

El agente no termina en una explicación: con la conclusión aceptada, separa las disputas que vale la pena pelear de las que no, redacta la respuesta al banco de cada una que vale pelear y deja todo en una cola de aprobación. **No envía nada.**

- **Qué disputas.** Si la pregunta nombra disputas, esas. Si es por un aumento, las del transportista y la región que el World Model ancló en la conclusión, en el período de la pregunta.
- **Con qué datos.** Las trae con `consultar(sql)`, como evidencia E#: la fila de cada disputa y los mensajes de soporte de sus pedidos.
- **Cómo separa.** Con la decisión de io-engine (`vale_pelear`, `razon_decision`).
- **Qué redacta.**
  - Una respuesta al banco por cada disputa que vale pelear, con entrega, historial del cliente, soporte y señales de fraude, cada dato con su E#.
  - Para un aumento, una entrada con la causa y qué disputas del grupo no conviene pelear, agrupadas por razón y con qué hacer con cada grupo.
- **Quién decide.** Mientras el agente corre no hay humano: la regla `politica_v1` aprueba o rechaza cada entrada y deja el motivo en `logs/cola_aprobacion.jsonl`. Solo aprueba sola lo que no tiene dudas (evidencia completa, disputa abierta, sin señales de fraude, monto hasta `AGENTE_POLITICA_MONTO_MAX`); lo demás lo rechaza para que lo decida una persona.

Las reglas y el formato están en [`CONTRATO.md`](CONTRATO.md). El informe muestra la cola en "Qué conviene hacer".

## Memoria entre corridas (H-MEM, de Meterless)

El agente no empieza de cero en cada corrida. Implementamos **H-MEM**, el motor de memoria de Meterless (`agente/memoria.py`, siguiendo `engines/hmem` del repo de Meterless):

- **Antes de la primera vuelta, recuerda.** Busca en su memoria con el ranking híbrido de H-MEM y le reinyecta al Investigador dos cosas:
  - las **lecciones del Evaluador**: cada motivo por el que antes le devolvieron un veredicto o una conclusión ("prueba al menos 2 hipótesis…", "cuenta las decisiones antes de recomendar…");
  - los **hallazgos** de corridas anteriores sobre esa misma pregunta, como pistas y nunca como evidencia: el Evaluador sigue exigiendo una consulta de esta corrida para cada afirmación.
- **Al terminar, aprende.**
  - Guarda las lecciones nuevas y, si concluyó, los hallazgos.
  - Reemplaza los hallazgos viejos de la misma pregunta: quedan penalizados, nunca se borran.
  - Sube o baja la confianza de lo que usó (+0.05 si ayudó, −0.03 si no).
  - Promueve a largo plazo lo que ayudó 3 veces.
- **Todo queda auditado**:
  - `memoria/memorias.json` guarda los registros con su fuente (`corrida:<run_id>`);
  - `memoria/ledger.jsonl` es el libro de confianza, de solo agregar, con el estado anterior y el nuevo de cada cambio;
  - en la traza quedan los eventos `recordar` y `aprender` del agente `memoria`.
- **Adaptador con tiempo límite y respaldo.** Si H-MEM está apagado (`AGENTE_HMEM=false`), tarda más de `AGENTE_HMEM_TIMEOUT_S` o falla, el agente sigue sin memoria y la traza lo dice (`omitido` o `error` con "respaldo").

## Qué se vio y de dónde salió (World Model, de Meterless)

H-MEM recuerda; el **World Model** lleva el registro canónico de las *cosas* que el agente vio en los datos. Lo implementamos siguiendo `engines/world-model` del repo de Meterless (`agente/mundo.py`):

- **Ingesta idempotente.** Cada consulta que devuelve filas pasa al World Model:
  - disputas, pedidos, pagos, envíos y clientes se guardan con su id de io-engine (`disputa:io:du_…`);
  - transportistas y regiones, con un id derivado del nombre normalizado (`ent_<sha256>`);
  - se guardan sus relaciones (disputa → pedido, transportista → región…) y sus hechos (`razon_decision`, `senales_fraude`…), con la corrida y la evidencia E# de donde salieron;
  - volver a ingerir las mismas filas no agrega nada.
- **Registro de solo agregar.** Todo vive en `mundo/eventos.jsonl` y el estado se reconstruye desde ahí. Una escritura sin procedencia se rechaza.
- **Anclaje de la conclusión.** Antes de aceptarla, el Evaluador le pregunta al World Model si cada disputa, transportista y región que nombra salió en una consulta de esta corrida. Si el modelo nombra algo que solo recuerda de otra corrida (H-MEM) o que inventó, se le devuelve. En la traza queda el evento `anclar`, con la evidencia de cada nombre: `RapidEnvio (E2); Norte (E2)`.
- **Resolución de ids.** Si una consulta no devuelve filas porque el modelo escribió mal un id (`du_…jgujrs` en vez de `du_…jgujrS`), el World Model le contesta con el id canónico.
- **Mismo adaptador con tiempo límite y respaldo** que H-MEM: con `AGENTE_MUNDO=false`, o si tarda o falla, el agente sigue sin anclaje ni resolución de ids, y la traza lo marca.

## Con y sin Meterless

```
python scripts/comparar_memoria.py
```

Corre los tres ejemplos con y sin Meterless (H-MEM y World Model). Por cada uno muestra vueltas, devoluciones del Evaluador, consultas, memorias reinyectadas, entidades ancladas y la traza en `logs/`. Las corridas con Meterless son reales, grabadas con los dos motores encendidos (`samples/corridas/*-hmem.json`), y arrancan de lo grabado en `samples/memoria/` y `samples/mundo/`.

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
- `logs/cola_aprobacion.jsonl`: la cola de aprobación, con lo que decidió la política para cada entrada y por qué,
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
- **Grabar corridas**: con todo lo del modo real levantado, `python scripts/grabar_corridas.py` corre los tres ejemplos, los graba en `samples/corridas/` (con memoria, como `*-hmem.json`) y regenera `ejemplos/`.
- **Consultas de la cola**: las que el agente arma solo (las disputas del grupo, los mensajes de soporte) se graban con `python scripts/completar_muestras.py`, con io-engine levantado y sin llamar al modelo.
- **Memoria y World Model**: en modo real viven en `memoria/` y `mundo/` (no se suben). `python scripts/sembrar_memoria.py` siembra la memoria con lo que enseñan las corridas ya grabadas, y `python scripts/congelar_memoria.py` copia las dos a `samples/`, lo que usa el modo de muestra.

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
| `AGENTE_POLITICA_MONTO_MAX` | `500` | monto (USD) hasta el que la política aprueba sola una respuesta al banco |
| `AGENTE_TOPE_DEVOLUCIONES` | `2` | veces que el Evaluador puede devolver una misma afirmación; después, el agente se abstiene |
| `AGENTE_HMEM` | `true` | H-MEM encendido; `false` corre sin memoria |
| `AGENTE_HMEM_TIMEOUT_S` | `2` | cada operación de memoria; si se pasa, sigue sin memoria |
| `AGENTE_HMEM_UMBRAL` | `0.30` | puntaje mínimo de un hallazgo para reinyectarse (las lecciones usan 0.20) |
| `AGENTE_MUNDO` | `true` | World Model encendido; `false` corre sin anclaje ni resolución de ids |
| `AGENTE_MUNDO_TIMEOUT_S` | `2` | cada operación del World Model; si se pasa, sigue sin él |

## Sponsors

- **Meterless:**
  - **Nightshift** es el proveedor principal de IA del agente (API compatible con OpenAI, con el contrato de Runtime de la guía), detrás de un adaptador con tiempo límite, reintentos y un modelo Nemotron de respaldo. Cada vuelta registra en la traza qué modelo respondió.
  - **H-MEM** es la memoria del agente entre corridas, y el **World Model** es el registro de lo que vio y de dónde salió (ver arriba).
  - **Qué se rompe si se quita Meterless:**
    - sin Nightshift, el agente no tiene modelo y se abstiene;
    - sin H-MEM, cada corrida empieza de cero: el Investigador repite errores que el Evaluador ya le había corregido (más devoluciones y vueltas);
    - sin World Model, el Evaluador ya no puede comprobar que lo que nombra la conclusión salió de una consulta de esa corrida, así que una disputa, transportista o región recordados o inventados pasan a la respuesta;
    - `python scripts/comparar_memoria.py` muestra la diferencia en `logs/`.
- **NVIDIA:** el modelo es Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`), servido a través de Nightshift.
- **Zetaris:** responde `consultar(sql)` en io-engine uniendo las tres fuentes sin copiarlas, con respaldo en DuckDB; cada respuesta registra qué motor respondió.
- **Herramienta de desarrollo:** ver `metadata.json`.

## License

PolyForm Noncommercial 1.0.0 · ver `LICENSE`.
