# Informe de IO · 20261023T171915-52be31

## La pregunta

> ¿Vale la pena pelear la disputa du_cuKtmopzODI37h?

## Lo que encontramos

Sí, vale la pena pelear la disputa du_cuKtmopzODI37h, por 129.9 dólares. El pedido fue entregado y confirmado con firma, el cliente no había reclamado antes y no hay indicios de fraude. Cumple todas las condiciones para ganarla.

- **Vale la pena pelear la disputa du_cuKtmopzODI37h porque el pedido fue entregado y confirmado, y el cliente no hizo un reclamo previo.** — En la fila 1 de la evidencia E1, el envío está entregado con prueba de entrega (firma), el cliente no hizo un reclamo previo, no hay señales de fraude y se indica que vale la pena pelear la disputa. (evidencia: E1)

## Hipótesis descartadas

- ~~No vale la pena pelear la disputa du_cuKtmopzODI37h porque hay sospecha de fraude en este caso.~~ — En la fila 1 de la evidencia E2, no hay señales de fraude ni sospecha de fraude, así que no hay fraude en este caso. (evidencia: E2)
- ~~No vale la pena pelear la disputa du_cuKtmopzODI37h porque el pedido no llegó o no hay prueba de entrega.~~ — En la fila 1 de la evidencia E3, el envío está entregado, no está extraviado y la prueba de entrega es firma, así que sí hay entrega y prueba de ella. (evidencia: E3)
- ~~No vale la pena pelear la disputa du_cuKtmopzODI37h porque el cliente ya había hecho un reclamo previo sobre este pedido.~~ — En la fila 1 de la evidencia E4, el cliente no hizo un reclamo previo sobre este pedido. (evidencia: E4)

## Evidencia

**E1** · motor: duckdb

```sql
SELECT disputa_id, motivo, monto, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, extraviado, reclamo_previo, senales_fraude, sospecha_fraude, vale_pelear, decision, razon_decision, causa_operativa FROM canonico.disputas WHERE disputa_id = 'du_cuKtmopzODI37h';
```

| disputa_id | motivo | monto | estado_envio | prueba_entrega | entregado_en | entrega_confirmada | extraviado | reclamo_previo | senales_fraude | sospecha_fraude | vale_pelear | decision | razon_decision | causa_operativa |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_cuKtmopzODI37h | unrecognized | 129.9 | entregado | firma | 2026-09-06 | True | False | False | 0 | False | True | pelear | entrega_confirmada_sin_reclamo | False |

**E2** · motor: duckdb

```sql
SELECT disputa_id, motivo, monto, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, extraviado, reclamo_previo, senales_fraude, sospecha_fraude, vale_pelear, decision, razon_decision, causa_operativa FROM canonico.disputas WHERE disputa_id = 'du_cuKtmopzODI37h';
```

| disputa_id | motivo | monto | estado_envio | prueba_entrega | entregado_en | entrega_confirmada | extraviado | reclamo_previo | senales_fraude | sospecha_fraude | vale_pelear | decision | razon_decision | causa_operativa |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_cuKtmopzODI37h | unrecognized | 129.9 | entregado | firma | 2026-09-06 | True | False | False | 0 | False | True | pelear | entrega_confirmada_sin_reclamo | False |

**E3** · motor: duckdb

```sql
SELECT disputa_id, motivo, monto, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, extraviado, reclamo_previo, senales_fraude, sospecha_fraude, vale_pelear, decision, razon_decision, causa_operativa FROM canonico.disputas WHERE disputa_id = 'du_cuKtmopzODI37h';
```

| disputa_id | motivo | monto | estado_envio | prueba_entrega | entregado_en | entrega_confirmada | extraviado | reclamo_previo | senales_fraude | sospecha_fraude | vale_pelear | decision | razon_decision | causa_operativa |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_cuKtmopzODI37h | unrecognized | 129.9 | entregado | firma | 2026-09-06 | True | False | False | 0 | False | True | pelear | entrega_confirmada_sin_reclamo | False |

**E4** · motor: duckdb

```sql
SELECT disputa_id, motivo, monto, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, extraviado, reclamo_previo, senales_fraude, sospecha_fraude, vale_pelear, decision, razon_decision, causa_operativa FROM canonico.disputas WHERE disputa_id = 'du_cuKtmopzODI37h';
```

| disputa_id | motivo | monto | estado_envio | prueba_entrega | entregado_en | entrega_confirmada | extraviado | reclamo_previo | senales_fraude | sospecha_fraude | vale_pelear | decision | razon_decision | causa_operativa |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_cuKtmopzODI37h | unrecognized | 129.9 | entregado | firma | 2026-09-06 | True | False | False | 0 | False | True | pelear | entrega_confirmada_sin_reclamo | False |


## Qué conviene hacer

Pelear la disputa presentando la prueba de entrega (firma) y el historial del cliente. Como es una sola disputa con entrega confirmada y sin reclamo previo, se recomienda pelearla en lugar de reembolsar o contactar al cliente.

---
Aprobación: **aprobada** · modo muestra · consultas: 4 · 45 ms
