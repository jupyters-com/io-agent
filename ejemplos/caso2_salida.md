# Informe de IO · 20261023T143418-45e62b

## La pregunta

> ¿Vale la pena pelear la disputa du_LRbXAOhoJgujrS?

## Lo que encontramos

No, no vale la pena pelear esta disputa de 489 dólares. Aunque el envío fue entregado con prueba de entrega y el cliente no hizo un reclamo previo, hay 4 señales de fraude: el cliente no tiene pedidos previos, el nivel de riesgo es el más alto, el país de facturación (CO) es distinto al país de la IP (NL), y el sistema detectó sospecha de fraude.

- **No vale la pena pelear la disputa porque hay múltiples señales de fraude y sospecha de fraude.** — La evidencia E3 registra 4 señales de fraude y sospecha_fraude=true, lo que impide pelear la disputa según la regla de vale_pelear. (evidencia: E3)

## Hipótesis descartadas

- ~~Vale la pena pelear la disputa porque el envío fue entregado con prueba de entrega y el cliente no hizo un reclamo previo.~~ — La evidencia E2 confirma entrega_confirmada=true y reclamo_previo=false, pero la evidencia E3 muestra senales_fraude=4 y sospecha_fraude=true. Como hay 2 o más señales de fraude, vale_pelear es false, por lo que no vale la pena pelear la disputa. (evidencia: E2, E3)

## Evidencia

**E1** · motor: duckdb

```sql
SELECT disputa_id, monto, motivo, estado, vale_pelear, decision, razon_decision, entrega_confirmada, reclamo_previo, senales_fraude, sospecha_fraude, pedidos_previos, disputas_previas, nivel_riesgo, pais_facturacion, pais_ip, prueba_entrega, estado_envio, causa_operativa FROM canonico.disputas WHERE disputa_id = 'du_LRbXAOhoJgujrS';
```

| disputa_id | monto | motivo | estado | vale_pelear | decision | razon_decision | entrega_confirmada | reclamo_previo | senales_fraude | sospecha_fraude | pedidos_previos | disputas_previas | nivel_riesgo | pais_facturacion | pais_ip | prueba_entrega | estado_envio | causa_operativa |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_LRbXAOhoJgujrS | 489.0 | fraudulent | needs_response | False | no_pelear | sospecha_de_fraude | True | False | 4 | True | 0 | 0 | highest | CO | NL | foto | entregado | False |

**E2** · motor: duckdb

```sql
SELECT entrega_confirmada, reclamo_previo FROM canonico.disputas WHERE disputa_id = 'du_LRbXAOhoJgujrS';
```

| entrega_confirmada | reclamo_previo |
| --- | --- |
| True | False |

**E3** · motor: duckdb

```sql
SELECT senales_fraude, sospecha_fraude FROM canonico.disputas WHERE disputa_id = 'du_LRbXAOhoJgujrS';
```

| senales_fraude | sospecha_fraude |
| --- | --- |
| 4 | True |


## Qué conviene hacer

No pelear la disputa. Aceptarla y marcar al cliente por sospecha de fraude.

---
Aprobación: **aprobada** · modo muestra · consultas: 3 · 7 ms
