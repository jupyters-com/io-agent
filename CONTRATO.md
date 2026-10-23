# Contrato del agente

Tres formatos fijos. Los esquemas formales están en `contrato/*.schema.json` y `agente/contrato.py` los valida, junto con las reglas de abajo. Las pruebas están en `tests/test_contrato.py`.

## 1. La respuesta (`contrato/respuesta.schema.json`)

Lo que devuelve `run.py` o `POST /run`, y lo que queda en `salidas/<run_id>.json`.

| Campo | Qué es |
| --- | --- |
| `run_id` | identifica la corrida; es el nombre de su traza en `logs/` |
| `pregunta` | la pregunta tal como llegó |
| `modo` | `muestra` o `real` |
| `estado` | `concluida` o `abstencion` |
| `conclusion` | una o dos frases; `null` si se abstiene |
| `hipotesis[]` | `id` (H1…), `enunciado`, `veredicto` (`sostenida` / `descartada` / `sin_decidir`), `razon`, `evidencia` (ids E1…) |
| `evidencia[]` | `id` (E1…), `sql`, `motor` que respondió, `ok`, `filas`, `n_filas`, `error`. Son las filas tal cual las devolvió `consultar(sql)` |
| `recomendacion` | qué conviene hacer; `null` si se abstiene |
| `abstencion` | `{razon}` cuando no concluye |
| `aprobacion` | `{item_id, estado}` de la conclusión en la cola |
| `cola` | las demás entradas de la cola: respuestas al banco, disputas que no conviene pelear y el grupo (ver 2) |
| `metricas` | iteraciones, consultas, ms, tokens, costo en USD, `devoluciones` (veces que el Evaluador devolvió algo), `memorias_usadas` (las que H-MEM reinyectó), `capa_semantica` (`on`/`off`, ver `SEMANTIC_LAYER`) y `entidades_ancladas` (lo que la conclusión nombra y el World Model encontró en la evidencia de la corrida) |
| `informe_md` | el informe legible (ver abajo) |

**Reglas que el esquema solo no expresa:**

1. `concluida` exige una conclusión y al menos una hipótesis **sostenida con evidencia**.
2. `abstencion` exige una razón y ninguna conclusión: el agente prefiere no concluir a inventar.
3. Toda hipótesis sostenida o descartada cita evidencia; toda evidencia citada existe y vino de una consulta exitosa.
4. El informe tiene sus cinco secciones.

### El informe legible (`informe_md`)

Para la dueña de la tienda, sin ver los logs. El video se graba sobre él (JPTRS-91). Secciones fijas:

1. **La pregunta**
2. **Lo que encontramos**: la conclusión con las hipótesis sostenidas, o la abstención y por qué
3. **Hipótesis descartadas**: tachadas, con la razón y la evidencia
4. **Evidencia**: cada consulta con su SQL, el motor que respondió y sus filas
5. **Qué conviene hacer**

## 2. La cola de aprobación (`contrato/aprobacion.schema.json`)

Ninguna respuesta sale sin pasar por la cola (`logs/cola_aprobacion.jsonl`, un ítem por línea), y la cola no envía nada: no hay banco ni procesador de pagos conectado. Es una cola lógica: mientras el agente corre no hay humano, y una regla de política (`politica_v1`, en `agente/cola.py`) aprueba o rechaza cada entrada y deja el motivo. Lo aprobado lo revisa y lo envía una persona.

Después de una conclusión aceptada, el agente prepara las entradas (`agente/preparador.py`):

| `tipo` | Qué es | Cómo la decide la política |
| --- | --- | --- |
| `conclusion` | lo que concluyó la investigación, o la abstención | aprobada si el Evaluador la aceptó; una abstención se rechaza (no hay nada que entregar) |
| `respuesta_banco` | el borrador de respuesta al banco de una disputa que vale pelear, con su evidencia (entrega, historial, soporte) | las 5 reglas de abajo |
| `no_pelear` | una disputa de la pregunta que no conviene pelear, y qué hacer en su lugar | aprobada si se apoya en evidencia (no se envía a nadie) |
| `grupo` | para un aumento: la causa y qué disputas del grupo no conviene pelear, por razón | igual; sin World Model no se puede delimitar el grupo y se rechaza |

Reglas de `politica_v1` para `respuesta_banco` (si falla alguna, se rechaza con el motivo):

1. `evidencia_completa`: entrega confirmada con firma o foto, y sin reclamo previo a soporte.
2. `disputa_abierta`: la disputa sigue esperando respuesta (`needs_response`).
3. `sin_senales_fraude`: 0 señales de fraude. Con alguna, aunque io-engine diga que vale pelear, la decide una persona.
4. `monto_tope`: monto hasta `AGENTE_POLITICA_MONTO_MAX` (500 USD).
5. `evidencia_citada`: el borrador cita las evidencias (E#) de las que sale.

| Campo | Qué es |
| --- | --- |
| `item_id` | `AP-<run_id>` para la conclusión, `AP-<run_id>-<n>` para las demás |
| `tipo` | `conclusion`, `respuesta_banco`, `no_pelear` o `grupo` |
| `disputa_id` | la disputa de la entrada (`null` en `conclusion` y `grupo`) |
| `estado` | `aprobada` o `rechazada` (`pendiente` queda para una decisión humana posterior) |
| `decidido_por` | `regla:politica_v1`; obligatorio si ya se decidió |
| `motivo` | por qué se decidió así |
| `reglas` | cada regla con `ok` y su detalle (en `respuesta_banco`) |
| `evidencia` | los E# en que se apoya |
| `resumen` | una línea |
| `borrador` | el texto preparado; nunca se envía solo |

La respuesta de la corrida trae la conclusión en `aprobacion` y las demás entradas en `cola[]` (`item_id`, `tipo`, `disputa_id`, `estado`, `motivo`, `borrador`), y el informe las muestra en "Qué conviene hacer". Los borradores salen de las filas con una plantilla: no inventan nada, no opinan de leyes ni de las reglas de las redes de tarjetas.

## 3. La evidencia (`logs/<run_id>.evidencia.jsonl`)

Una línea por consulta, con lo mismo que `evidencia[]` de la respuesta (`id`, `sql`, `motor`, `ok`, `filas`, `n_filas`, `error`) más `run_id` e `hipotesis` (la que esa consulta probaba). Es la "fila de evidencia" que se muestra en pantalla.

## 4. La traza (`contrato/traza.schema.json`)

`logs/<run_id>.jsonl`, un evento por línea. La escriben el orquestador, el investigador (Paso 10), el evaluador (Paso 10b), la cola, la memoria (H-MEM) y el mundo (World Model), estos dos del Paso 13.

| Campo | Qué es |
| --- | --- |
| `paso` | orden del evento en la corrida (1, 2, 3…) |
| `agente` | `orquestador`, `investigador`, `evaluador`, `cola`, `memoria` o `mundo` |
| `destino` | a quién le habla: `io-engine.consultar`, `modelo`, `cola_aprobacion`, `salida`… |
| `accion` | qué hizo: `recibir_pregunta`, `pensar`, `proponer_hipotesis`, `revisar_hipotesis`, `preparar`, `consultar`, `revisar_veredicto`, `devolver`, `descartar`, `sostener`, `revisar_conclusion`, `tope_devoluciones`, `recordar`, `aprender`, `abrir_corrida`, `ingerir`, `anclar`, `resolver`, `encolar`, `entregar`, `tope_iteraciones`, `alerta_gasto` |
| `entrada` / `salida` | resumen de lo que entró y salió (máx. 300 caracteres) |
| `estado` | `ok`, `error`, `alerta` u `omitido` |
| `reintentos` | cuántas veces se reintentó; en `revisar_veredicto` y `revisar_conclusion`, cuántas veces el Evaluador ya había devuelto esa misma afirmación. Pasado `AGENTE_TOPE_DEVOLUCIONES` (2), el agente se abstiene (`tope_devoluciones`) |
| `ms` | cuánto tardó |
