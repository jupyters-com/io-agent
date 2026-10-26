# io-agent · el agente de IO para contracargos

**Idioma:** [English](README.md) · Español

Agente que investiga por qué suben las disputas de pago: propone explicaciones, las prueba con datos y descarta las que la evidencia no sostiene, dejando anotada cada prueba. Si no puede sostener una conclusión con filas, se abstiene.

Construido durante el Open Agent Hackathon 2026 (Track 02 · *The Agent That Can Explain Why*), desde el 22-oct-2026. Todo lo que está en este repo es trabajo nuevo del hackathon.

> **Léelo primero: el modo de muestra es el valor por defecto.** `SAMPLE_MODE=true` repite **corridas reales grabadas**: lo que respondió Nemotron (vía Meterless Nightshift) y las filas que devolvió io-engine, para las tres preguntas de ejemplo de `ejemplos/`. La lógica del agente (Investigador, Evaluador, cola de aprobación, memoria) corre de verdad sobre esas grabaciones; no se llama al modelo ni al motor de datos. Cualquier otra pregunta no tiene grabación y el agente se abstiene. Para preguntas nuevas, usa el modo real (sección «Modo real: preguntas nuevas»). Los datos son sintéticos.
>
> Los organizadores confirmaron que es aceptable: *"yes a pre-recorded sample mode acceptable, please make sure its highlighted in your submission and README"* (Janson Lim, HackOS #Help desk, 24-oct-2026).

## Probarlo en 2 minutos

No hace falta ninguna clave, ni el modelo, ni el motor de datos. Por defecto el agente corre en **modo de muestra**: repite corridas **reales** grabadas (lo que respondió Nemotron vía Meterless Nightshift y las filas que devolvió io-engine, tal cual) y responde en milisegundos. La traza, la evidencia, el informe y la cola de aprobación son los de esa corrida real.

Con Python 3.12 o más nuevo:

```
pip install -r requirements.txt
python run.py ejemplos/caso3_entrada.json
```

O con Docker (corre el caso 3):

```
docker compose run --rm agente
```

El informe legible queda en `salidas/<run_id>.md`. Ese es el archivo para leer.

### Las preguntas que responde el modo de muestra

| Archivo | Pregunta | Qué muestra |
| --- | --- | --- |
| `ejemplos/caso1_entrada.json` | ¿Vale la pena pelear la disputa du_cuKtmopzODI37h? | **Sí**: entregada con firma, sin reclamo previo, sin señales de fraude. Deja la respuesta al banco en la cola. |
| `ejemplos/caso2_entrada.json` | ¿Vale la pena pelear la disputa du_LRbXAOhoJgujrS? | **No**: aunque llegó con foto, tiene 4 señales de fraude. Descarta la hipótesis contraria con evidencia. |
| `ejemplos/caso3_entrada.json` | ¿Por qué subieron las disputas en la segunda quincena de septiembre de 2026? | El pico (de 4 a 18) no es fraude: lo explica RapidEnvio en el Norte (14 de 18). Separa qué disputas pelear y redacta sus respuestas; la política rechaza una (`du_HlcQ…`, 1 señal de fraude) para que la decida una persona. |

Las salidas de estas tres corridas ya están en `ejemplos/*_salida.md`, por si se quieren leer sin correr nada.

**Una pregunta distinta** (o escrita distinto: se ignoran mayúsculas y espacios, pero no otras palabras) no tiene una corrida grabada, y el agente **se abstiene** en vez de inventar: "No hay una corrida grabada (o se terminó) para esta pregunta en modo de muestra. Para preguntas nuevas usa el modo real / For new questions use live mode: SAMPLE_MODE=false (README.md, «Live mode: new questions»; README.es.md, «Modo real: preguntas nuevas»)." Para preguntas nuevas está el modo real (abajo).

### Las comparaciones, también al instante

```
python scripts/comparar_capa.py        # la misma pregunta con y sin la capa de IO
python scripts/comparar_memoria.py     # con y sin Meterless (H-MEM y World Model)
```

- `comparar_capa.py` deja el lado a lado en [`ejemplos/comparacion_capa.md`](ejemplos/comparacion_capa.md). Sin la capa, el caso 1 dice "no pelear" a una disputa que se podía ganar, porque no logra cruzar el pedido entre sistemas.
- La medición sobre las 42 disputas del set de prueba ya está en [`evaluacion/medicion.md`](evaluacion/medicion.md): **42 de 42 con la capa, 8 de 42 sin ella**. Volver a correrla necesita el modo real, porque son preguntas nuevas. Cómo leerla: el 42 de 42 mide que el agente reproduce la definición del set (`vale_pelear`, del esquema canónico), no una verdad externa; y las 20 defensas perdidas sin la capa son un solo error repetido (no cruza `ORD-1574` con `1574`), no 20 errores distintos.

### Como servicio

```
python run.py --servir
```

Y un `POST http://localhost:8080/run` con, por ejemplo, `{"pregunta": "¿Vale la pena pelear la disputa du_cuKtmopzODI37h?"}`.

### Qué deja cada corrida

- `logs/<run_id>.jsonl`: la traza, un evento por línea (quién hizo qué, con qué evidencia, cuánto tardó);
- `logs/<run_id>.evidencia.jsonl`: cada consulta con sus filas y la hipótesis que probaba;
- `logs/cola_aprobacion.jsonl`: la cola, con lo que decidió la política para cada entrada y por qué;
- `salidas/<run_id>.json` y `.md`: la respuesta y el informe.

### Modo real: preguntas nuevas

Para preguntar cualquier cosa, el agente necesita sus dos dependencias levantadas:

1. **io-engine**, el motor de datos (componente previo, otro repo): `docker compose up` en ese repo.
2. **Meterless Nightshift** con un lane de NVIDIA Nemotron y su token de Runtime.

Copia `.env.example` como `.env.local`, completa `METERLESS_RUNTIME_TOKEN` y pon `SAMPLE_MODE=false`. Después, guarda la pregunta en un archivo (por ejemplo `mi_pregunta.json` con `{"pregunta": "..."}`) y corre `python run.py mi_pregunta.json`. En macOS o Linux también vale `python run.py '{"pregunta": "..."}'`.

**Una pregunta en modo real tarda de 1 a 8 minutos.** Nemotron razona antes de cada respuesta, una investigación son de 2 a 6 vueltas con el modelo, y Nightshift corta cada llamada a los 45 segundos (el agente la reintenta, y si sigue fallando pasa a un Nemotron de respaldo). Por eso la demo se ve en modo de muestra.

## Cómo investiga

El **Investigador** conversa con el modelo (Nemotron, vía Meterless Nightshift). En cada vuelta el modelo responde una acción en JSON y nuestro código la ejecuta y la anota:

1. **Propone hipótesis** (H1, H2…), incluida la explicación más obvia aunque sea falsa (por ejemplo, "es fraude").
2. **Las prueba** con `consultar(sql)` contra io-engine. Cada resultado queda como evidencia E1, E2…
3. **Da un veredicto** (sostenida o descartada) citando la evidencia. El **Evaluador** lo revisa y lo devuelve si la evidencia no existe, falló o no trae filas.
4. **Concluye** solo si el Evaluador acepta: todas las hipótesis con veredicto y al menos una sostenida. Si los datos no alcanzan, **se abstiene**.

Todo lo que sale en el informe (enunciados, razones, conclusión y recomendación) lo lee la dueña de la tienda, así que el Evaluador también devuelve lo que trae términos técnicos (`product_not_received`, `zona_con_atrasos=true`). Si devuelve la misma cosa más de `AGENTE_TOPE_DEVOLUCIONES` veces, el agente se abstiene.

La IA piensa; el código hace y registra. Topes: `AGENTE_MAX_ITERACIONES` vueltas y `AGENTE_TIMEOUT_S` por llamada.

## Con y sin la capa de IO

El diferencial de IO es la capa semántica: la misma pregunta responde mal sobre las fuentes crudas y bien con la capa. Un interruptor lo muestra:

```
SEMANTIC_LAYER=off
```

Con la capa apagada, el agente consulta las tablas crudas de io-engine (`crudo.pagos_disputes`, `crudo.envios`, `crudo.soporte_tickets`…), tal como llegan de cada sistema:

- montos en centavos y fechas en distintos formatos;
- pedidos escritos como `ORD-1574`, `1574` o `#1574`;
- el soporte, ligado por correo y no por cliente.

Además queda **sin** el esquema canónico, **sin** sus definiciones (qué es entrega confirmada, reclamo previo, zona con atrasos o señal de fraude) y **sin** Meterless (H-MEM y World Model). Todo lo demás es igual: mismo modelo, misma pregunta, mismos datos y el mismo Evaluador, salvo las reglas que usan definiciones de la capa.

```
python scripts/comparar_capa.py
```

Corre los tres ejemplos con y sin la capa y deja el lado a lado en [`ejemplos/comparacion_capa.md`](ejemplos/comparacion_capa.md), con las dos trazas en `logs/`. Las corridas sin capa se graban con `SEMANTIC_LAYER=off python scripts/grabar_corridas.py` (en Windows: `set SEMANTIC_LAYER=off` antes) y quedan como `samples/corridas/*-sincapa.json`.

### Con números: el set de prueba

Además de los tres casos de la demo, el agente se mide sobre todas las disputas de los datos sintéticos, cada una con su respuesta esperada según la definición del esquema canónico (vale la pena pelear, no vale la pena o causa operativa):

```
python scripts/armar_set_prueba.py           # evaluacion/set_prueba.csv y .md (con io-engine levantado)
python scripts/medir_set.py --primeros 5      # prueba corta
python scripts/medir_set.py                   # el set completo, con y sin la capa (se puede cortar y retomar)
```

La tabla con los dos resultados lado a lado queda en `evaluacion/medicion.md`: aciertos, defensas que no debían armarse, defensas perdidas y abstenciones con su razón. Las respuestas quedan en `evaluacion/resultados/` y las trazas en `evaluacion/logs/`.

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
- **Qué muestra y qué no.** `comparar_memoria.py` muestra que el agente recuerda lo que el Evaluador le corrigió antes (menos devoluciones y vueltas al repetir la misma pregunta). No prueba que esa memoria generalice a preguntas nuevas.

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

Corren sin red ni claves. La mayoría usa un modelo de guion y un motor falso (`tests/falsos.py`) para probar cada pieza: el ciclo del Investigador, el Evaluador, H-MEM, el World Model, la cola y su política, el interruptor de la capa y la medición. `tests/test_investigador_rojo.py` repite las corridas grabadas de los tres casos y comprueba sus conclusiones.

## Topes

| Variable | Por defecto | Qué limita |
| --- | --- | --- |
| `AGENTE_TIMEOUT_S` | `60` | cada llamada externa (motor y modelo), con un reintento si se pasa |
| `AGENTE_MAX_ITERACIONES` | `16` | vueltas con el modelo por corrida |
| `AGENTE_PRESUPUESTO_USD` | `1.0` | gasto en el proveedor del modelo: si se pasa, queda una alerta en la traza |
| `SEMANTIC_LAYER` | `on` | `off` apaga la capa de IO: tablas crudas, sin definiciones ni Meterless (para comparar) |
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
