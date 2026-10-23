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
| `aprobacion` | `{item_id, estado}` del ítem en la cola |
| `metricas` | iteraciones, consultas, ms, tokens, costo en USD, `devoluciones` (veces que el Evaluador devolvió algo), `memorias_usadas` (las que H-MEM reinyectó) y `entidades_ancladas` (lo que la conclusión nombra y el World Model encontró en la evidencia de la corrida) |
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

Ninguna respuesta sale sin pasar por la cola (`logs/cola_aprobacion.jsonl`, un ítem por línea). Es una cola lógica: el agente no se pausa esperando a una persona.

| Campo | Qué es |
| --- | --- |
| `item_id` | `AP-<run_id>` |
| `estado` | `pendiente`, `aprobada` o `rechazada` |
| `decidido_por` | `regla:<nombre>` o `humano:<correo>`; obligatorio si ya se decidió |
| `motivo` | por qué se decidió así |
| `resumen` | la conclusión o la razón de abstención, en una línea |

Con `SAMPLE_MODE=true`, la regla `auto_muestra` aprueba y queda registrado. En modo real el ítem queda `pendiente` (la decisión humana es el Paso 11, JPTRS-60).

## 3. La evidencia (`logs/<run_id>.evidencia.jsonl`)

Una línea por consulta, con lo mismo que `evidencia[]` de la respuesta (`id`, `sql`, `motor`, `ok`, `filas`, `n_filas`, `error`) más `run_id` e `hipotesis` (la que esa consulta probaba). Es la "fila de evidencia" que se muestra en pantalla.

## 4. La traza (`contrato/traza.schema.json`)

`logs/<run_id>.jsonl`, un evento por línea. La escriben el orquestador, el investigador (Paso 10), el evaluador (Paso 10b), la cola, la memoria (H-MEM) y el mundo (World Model), estos dos del Paso 13.

| Campo | Qué es |
| --- | --- |
| `paso` | orden del evento en la corrida (1, 2, 3…) |
| `agente` | `orquestador`, `investigador`, `evaluador`, `cola`, `memoria` o `mundo` |
| `destino` | a quién le habla: `io-engine.consultar`, `modelo`, `cola_aprobacion`, `salida`… |
| `accion` | qué hizo: `recibir_pregunta`, `pensar`, `proponer_hipotesis`, `revisar_hipotesis`, `consultar`, `revisar_veredicto`, `devolver`, `descartar`, `sostener`, `revisar_conclusion`, `tope_devoluciones`, `recordar`, `aprender`, `abrir_corrida`, `ingerir`, `anclar`, `resolver`, `encolar`, `entregar`, `tope_iteraciones`, `alerta_gasto` |
| `entrada` / `salida` | resumen de lo que entró y salió (máx. 300 caracteres) |
| `estado` | `ok`, `error`, `alerta` u `omitido` |
| `reintentos` | cuántas veces se reintentó; en `revisar_veredicto` y `revisar_conclusion`, cuántas veces el Evaluador ya había devuelto esa misma afirmación. Pasado `AGENTE_TOPE_DEVOLUCIONES` (2), el agente se abstiene (`tope_devoluciones`) |
| `ms` | cuánto tardó |
