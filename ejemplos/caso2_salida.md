# Informe de IO · 20261023T190428-59cb51

## La pregunta

> ¿Vale la pena pelear la disputa du_LRbXAOhoJgujrS?

## Lo que encontramos

No, no vale la pena pelear la disputa du_LRbXAOhoJgujrS de 489 dólares. El pedido llegó y hay una foto como prueba de entrega, y el cliente no había hecho un reclamo previo sobre este pedido. Sin embargo, se detectaron 4 señales de fraude y el cliente está bajo sospecha de fraude, por lo que no se debe pelear.

- **No vale la pena pelear la disputa du_LRbXAOhoJgujrS porque el cliente está bajo sospecha de fraude.** — La evidencia E2 (1 fila) muestra que el cliente tiene 4 señales de fraude y está bajo sospecha de fraude. Con 4 señales de fraude (2 o más), no se debe pelear esta disputa. (evidencia: E2)

## Hipótesis descartadas

- ~~Vale la pena pelear la disputa du_LRbXAOhoJgujrS porque el pedido fue entregado y confirmado, y el cliente no hizo un reclamo previo sobre este pedido.~~ — La evidencia E1 (1 fila) confirma que el pedido fue entregado y hay una foto como prueba de entrega, y que el cliente no había hecho un reclamo previo. Pero la misma fila registra 4 señales de fraude y el cliente está bajo sospecha de fraude, por lo que la decisión es no pelear. Con 4 señales de fraude (2 o más), no vale la pena pelear aunque haya entrega confirmada. (evidencia: E1)

## Evidencia

**E1** · motor: duckdb

```sql
SELECT disputa_id, motivo, monto, estado_envio, prueba_entrega, entregado_en, reclamo_previo, senales_fraude, sospecha_fraude, vale_pelear, decision, razon_decision FROM canonico.disputas WHERE disputa_id = 'du_LRbXAOhoJgujrS';
```

| disputa_id | motivo | monto | estado_envio | prueba_entrega | entregado_en | reclamo_previo | senales_fraude | sospecha_fraude | vale_pelear | decision | razon_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_LRbXAOhoJgujrS | fraudulent | 489.0 | entregado | foto | 2026-09-13 | False | 4 | True | False | no_pelear | sospecha_de_fraude |

**E2** · motor: duckdb

```sql
SELECT disputa_id, motivo, monto, estado_envio, prueba_entrega, entregado_en, reclamo_previo, senales_fraude, sospecha_fraude, vale_pelear, decision, razon_decision FROM canonico.disputas WHERE disputa_id = 'du_LRbXAOhoJgujrS';
```

| disputa_id | motivo | monto | estado_envio | prueba_entrega | entregado_en | reclamo_previo | senales_fraude | sospecha_fraude | vale_pelear | decision | razon_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_LRbXAOhoJgujrS | fraudulent | 489.0 | entregado | foto | 2026-09-13 | False | 4 | True | False | no_pelear | sospecha_de_fraude |

**E3** · motor: duckdb

```sql
SELECT razon_decision, count(*) as cantidad FROM canonico.disputas GROUP BY razon_decision;
```

| razon_decision | cantidad |
| --- | --- |
| sin_prueba_de_entrega | 3 |
| sospecha_de_fraude | 3 |
| sin_entrega | 4 |
| entrega_confirmada_sin_reclamo | 20 |
| reclamo_previo | 12 |

**E4** · motor: duckdb

```sql
SELECT razon_decision, count(*) as cantidad FROM canonico.disputas GROUP BY razon_decision;
```

| razon_decision | cantidad |
| --- | --- |
| sin_prueba_de_entrega | 3 |
| sospecha_de_fraude | 3 |
| sin_entrega | 4 |
| entrega_confirmada_sin_reclamo | 20 |
| reclamo_previo | 12 |

**E5** · motor: duckdb

```sql
SELECT disputa_id, pedido_id, cliente_id, motivo, estado, monto, abierta_en, vence_en, transportista, region, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, reclamo_previo, pedidos_previos, disputas_previas, senales_fraude, vale_pelear, razon_decision FROM canonico.disputas WHERE disputa_id IN ('du_LRbXAOhoJgujrS') ORDER BY disputa_id
```

| disputa_id | pedido_id | cliente_id | motivo | estado | monto | abierta_en | vence_en | transportista | region | estado_envio | prueba_entrega | entregado_en | entrega_confirmada | reclamo_previo | pedidos_previos | disputas_previas | senales_fraude | vale_pelear | razon_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_LRbXAOhoJgujrS | ORD-1650 | cus_YFoGrpQQqoavsM | fraudulent | needs_response | 489.0 | 2026-09-18 15:00:00 | 2026-10-02 23:00:00 | PaqueteYa | Sur | entregado | foto | 2026-09-13 | True | False | 0 | 0 | 4 | False | sospecha_de_fraude |


## Qué conviene hacer

No pelear esta disputa; aceptarla y marcar al cliente por sospecha de fraude. De las 1 disputas del grupo, 1 se debe aceptar por sospecha de fraude y marcar al cliente.

### Cola de aprobación

IO prepara y no envía nada: una regla de política aprueba o rechaza cada entrada, y lo aprobado lo revisa y lo envía una persona.

**No pelear · du_LRbXAOhoJgujrS** · ✅ aprobada · `AP-20261023T190428-59cb51-1`

_Política: no se envía al banco: es el plan para la dueña, con su evidencia_

> Disputa du_LRbXAOhoJgujrS · 489.00 USD: no conviene pelearla porque hay 2 o más señales de fraude. Qué hacer: no pelear: aceptar la disputa y marcar al cliente. [E5]

---
Aprobación: **aprobada** · modo muestra · consultas: 5 · 98 ms
