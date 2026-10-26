# Informe de IO · 20261023T190427-46c33f

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

**E5** · motor: duckdb

```sql
SELECT disputa_id, pedido_id, cliente_id, motivo, estado, monto, abierta_en, vence_en, transportista, region, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, reclamo_previo, pedidos_previos, disputas_previas, senales_fraude, vale_pelear, razon_decision FROM canonico.disputas WHERE disputa_id IN ('du_cuKtmopzODI37h') ORDER BY disputa_id
```

| disputa_id | pedido_id | cliente_id | motivo | estado | monto | abierta_en | vence_en | transportista | region | estado_envio | prueba_entrega | entregado_en | entrega_confirmada | reclamo_previo | pedidos_previos | disputas_previas | senales_fraude | vale_pelear | razon_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_cuKtmopzODI37h | ORD-1574 | cus_3QyF0zEKBVKKDb | unrecognized | needs_response | 129.9 | 2026-09-29 15:00:00 | 2026-10-13 23:00:00 | CargoSur | Centro | entregado | firma | 2026-09-06 | True | False | 4 | 0 | 0 | True | entrega_confirmada_sin_reclamo |

**E6** · motor: duckdb

```sql
SELECT pedido_id, creado_en, categoria, texto FROM canonico.mensajes_soporte WHERE pedido_id IN ('ORD-1574') ORDER BY pedido_id, creado_en
```

_(sin filas)_


## Qué conviene hacer

Pelear la disputa presentando la prueba de entrega (firma) y el historial del cliente. Como es una sola disputa con entrega confirmada y sin reclamo previo, se recomienda pelearla en lugar de reembolsar o contactar al cliente.

### Cola de aprobación

IO prepara y no envía nada: una regla de política aprueba o rechaza cada entrada, y lo aprobado lo revisa y lo envía una persona.

**Respuesta al banco · du_cuKtmopzODI37h** · ✅ aprobada · `AP-20261023T190427-46c33f-1`

_Política: cumple las 5 reglas de la política: queda lista para que una persona la envíe_

> Respuesta a la disputa du_cuKtmopzODI37h · cargo no reconocido · 129.90 USD · abierta el 2026-09-29 · vence el 2026-10-13
>
> Solicitamos que se mantenga el cargo. Evidencia:
> - Entrega: el pedido ORD-1574 se entregó el 2026-09-06 con CargoSur (Centro), con firma de quien recibió. [E5]
> - Historial del cliente: 4 pedidos anteriores y ninguna disputa previa. [E5]
> - Soporte: el cliente no escribió a soporte sobre este pedido. [E6]
> - Señales de fraude: 0 de 4 (cliente nuevo, riesgo alto, país de la IP distinto, punto de retiro). [E5]
>
> Adjuntar: comprobante de entrega (firma de quien recibió) y el historial de comunicaciones con el cliente.
> Borrador preparado por IO con datos de io-engine. Lo revisa y lo envía una persona.

---
Aprobación: **aprobada** · modo muestra · consultas: 6 · 154 ms
