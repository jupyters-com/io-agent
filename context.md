# Contexto del proyecto (para quien trabaje en este repo, persona o agente de código)

## Qué es IO

IO investiga por qué pasan las cosas en los datos de una tienda online. El caso del hackathon son los **contracargos** (disputas de pago): ante una pregunta como "¿por qué subieron las disputas en septiembre?", el agente propone explicaciones, las prueba con datos y descarta las que la evidencia no sostiene, dejando anotada cada prueba. Track 02 del Open Agent Hackathon 2026: *The Agent That Can Explain Why*.

## Reglas que no se rompen

1. **El agente solo ve datos a través de `consultar(sql)`** del motor `io-engine` (por MCP). Nunca lee archivos ni bases directamente.
2. **No se copia código del motor aquí.** `io-engine` es componente previo (tag `previo-22oct`); este repo es solo trabajo nuevo, desde el 22-oct-2026.
3. **Sin evidencia no hay conclusión.** Si el agente no puede sostener una hipótesis con filas, se abstiene. La abstención es parte del producto, no un error.
4. **Toda respuesta pasa por la cola de aprobación** y todo paso queda en la traza JSONL (ver `CONTRATO.md`).
5. **Claves solo en `.env.local`**, nunca en el código, en los logs ni en los commits. La clave de NVIDIA vive en Nightshift, no aquí.
6. **`SAMPLE_MODE=true` siempre debe correr** desde un clon limpio, sin credenciales y sin el motor.
7. Datos sintéticos (semilla 2026, correos `@ejemplo.test`). Nada de datos reales.

## El esquema que ve el agente

Cinco tablas en `canonico` (iguales en DuckDB y en Zetaris): `clientes`, `pagos`, `envios`, `mensajes_soporte` y `disputas`. Las definiciones están en `io-engine/dbt_io/models/canonico/definiciones.md`. Zetaris devuelve los valores como texto y DuckDB con su tipo.

## Los tres casos plantados (la historia de la demo)

1. **Una disputa que vale la pena pelear:** cliente fiel, entrega con firma, sin reclamo previo.
2. **Un fraude real:** cliente nuevo, riesgo alto, país de la IP distinto, entrega en punto de retiro.
3. **El pico de la segunda quincena de septiembre:** lo explica RapidEnvio en el Norte (entregas tarde o extraviadas y reclamos previos), no una ola de fraude.

## Piezas y pasos

| Pieza | Paso | Estado |
| --- | --- | --- |
| Esqueleto, contrato, traza, cola, modo de muestra | 9 (JPTRS-55) | hecho |
| Investigador que descarta hipótesis (`agente/investigador.py`) | 10 (JPTRS-67) | hecho; faltan las corridas grabadas de los 3 casos |
| Evaluador que rechaza sin evidencia (`agente/evaluador.py`) | 10b (JPTRS-87) | versión mínima; falta endurecerlo |
| Cola de aprobación con decisión humana | 11 (JPTRS-60) | pendiente |
| Meterless (World Model / H-MEM) dentro del agente | 13 (JPTRS-68) | pendiente |

## Sponsors

- **Meterless Nightshift** es el proveedor principal de IA del agente, con **NVIDIA Nemotron** como modelo.
- **Zetaris** es uno de los dos motores de `consultar(sql)` en `io-engine`, con respaldo en DuckDB.
