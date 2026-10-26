# Medición: el agente con y sin la capa de IO sobre el set de prueba

Set: `evaluacion/set_prueba.csv` (42 disputas con su respuesta esperada, según la definición del esquema canónico). A cada una se le preguntó al agente "¿Vale la pena pelear la disputa …?" con la capa encendida y apagada (`SEMANTIC_LAYER`), en modo real: mismo modelo, mismos datos. Generado con `python scripts/medir_set.py`; las respuestas están en `evaluacion/resultados/` y las trazas en `evaluacion/logs/`.

| | Con la capa de IO | Sin la capa |
| --- | --- | --- |
| **Disputas medidas** | 42 | 42 |
| **Aciertos (decisión y razón correctas)** | 42 | 8 |
| **% de acierto** | 100.0 % | 19.0 % |
| **Decisión correcta por una razón falsa ("no hubo entrega" cuando sí la hubo)** | 0 | 14 |
| **% de decisión correcta, sin mirar la razón** | 100.0 % | 52.4 % |
| **Defensas que no debían armarse** | 0 | 0 |
| **Defensas perdidas (convenía pelear y dijo que no)** | 0 | 20 |
| **Abstenciones** | 0 | 0 |
| **Sin clasificar** | 0 | 0 |

**Defensas perdidas sin la capa:** 20 disputas que convenía pelear, por 2,359.45 USD en total; 4 siguen esperando respuesta (377.57 USD).

## Cómo leer estos números

* **Qué mide el 42 de 42.** Que el agente con la capa reproduce la definición del set (`vale_pelear` y `razon_decision` del esquema canónico). El set sale de esa misma definición, así que no es una verdad externa ni una medida de acierto en datos reales.
* **Las 20 defensas perdidas son un solo error repetido.** Sin la capa, el agente no cruza el pedido `ORD-1574` (pagos) con `1574` (logística), ve la entrega vacía y concluye que no hay prueba. No son 20 errores distintos.
* **Datos sintéticos.** Las 42 disputas salen de los datos de demostración de io-engine.

## Disputa por disputa

| disputa | esperada | con la capa | sin la capa |
| --- | --- | --- | --- |
| du_1jmfZda6WdIoKx | vale la pena pelear | acierto | defensa perdida |
| du_3COvpQYbwwTYH2 | no vale la pena | acierto | acierto |
| du_3OD4LlsutTnMwA | vale la pena pelear | acierto | defensa perdida |
| du_4JlZy1mEwyYk0o | vale la pena pelear | acierto | defensa perdida |
| du_4hOqdfYSu4AOg3 | vale la pena pelear | acierto | defensa perdida |
| du_6F59FMva3JVQxJ | causa operativa | acierto | acierto con una razón falsa |
| du_9dWJYUeeturRnn | causa operativa | acierto | acierto con una razón falsa |
| du_Ba2kQysmCVNVGZ | vale la pena pelear | acierto | defensa perdida |
| du_CEMNjn58fdMGmD | causa operativa | acierto | acierto con una razón falsa |
| du_DsQvAQr7hIoFPI | vale la pena pelear | acierto | defensa perdida |
| du_GZ5cJR2XsQLiVZ | vale la pena pelear | acierto | defensa perdida |
| du_GwJYLPbbPgPC7r | causa operativa | acierto | acierto con una razón falsa |
| du_HlcQBjPyAHVnB0 | vale la pena pelear | acierto | defensa perdida |
| du_HzRV7MU4HKE0Yk | no vale la pena | acierto | acierto con una razón falsa |
| du_IgNsS8yf9bEV9P | causa operativa | acierto | acierto |
| du_J2VkKpQXqpe4KC | causa operativa | acierto | acierto con una razón falsa |
| du_KntafjWlp0S39V | no vale la pena | acierto | acierto |
| du_LHXBZK1JYA14wp | vale la pena pelear | acierto | defensa perdida |
| du_LOPZTf9DyTmhq6 | no vale la pena | acierto | acierto con una razón falsa |
| du_LRbXAOhoJgujrS | no vale la pena | acierto | acierto con una razón falsa |
| du_N03jJfCP8hro0S | no vale la pena | acierto | acierto con una razón falsa |
| du_OELLdXYaGxqjJ1 | causa operativa | acierto | acierto con una razón falsa |
| du_PMAZj7wHYofcca | causa operativa | acierto | acierto |
| du_PNg3eecIE6roFO | vale la pena pelear | acierto | defensa perdida |
| du_Pp1eEgbk45lq8i | causa operativa | acierto | acierto con una razón falsa |
| du_Q3xt6xt6NmWypp | vale la pena pelear | acierto | defensa perdida |
| du_SdC1lwZa8XqujK | causa operativa | acierto | acierto con una razón falsa |
| du_SnubmlwGQ4HEzO | vale la pena pelear | acierto | defensa perdida |
| du_YiCss9xvTVSFfo | no vale la pena | acierto | acierto |
| du_ZBvx28srntoGXW | vale la pena pelear | acierto | defensa perdida |
| du_ZaTDySGw8g3aWP | vale la pena pelear | acierto | defensa perdida |
| du_aTLi4ieVtbQuvL | vale la pena pelear | acierto | defensa perdida |
| du_bkyZTavw3lFtW7 | vale la pena pelear | acierto | defensa perdida |
| du_cuKtmopzODI37h | vale la pena pelear | acierto | defensa perdida |
| du_fy30v6Y1zyMQ6G | causa operativa | acierto | acierto |
| du_gnaAFPejrbqvaO | vale la pena pelear | acierto | defensa perdida |
| du_gxP70mHojPHnGI | causa operativa | acierto | acierto |
| du_lssUuJfReewvtB | no vale la pena | acierto | acierto |
| du_tpw970A01kVWEq | no vale la pena | acierto | acierto con una razón falsa |
| du_vju1es2xtIlqD0 | no vale la pena | acierto | acierto con una razón falsa |
| du_x7zxADO5vb36t0 | vale la pena pelear | acierto | defensa perdida |
| du_zZT5tciTHKDN7Y | vale la pena pelear | acierto | defensa perdida |
