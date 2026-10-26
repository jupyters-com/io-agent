# Informe de IO · 20261023T141944-eeac17

## La pregunta

> ¿Vale la pena pelear la disputa du_cuKtmopzODI37h?

## Lo que encontramos

Sí, vale la pena pelear esta disputa de 129.9 dólares. El pedido fue entregado y confirmado con firma, el cliente no había reclamado antes sobre este pedido, no hay señales de fraude (mismo país de facturación y de IP, cliente con historial y riesgo normal), y ya tiene 4 pedidos previos sin ninguna disputa anterior. Cumple todas las condiciones para ganarla.

- **Vale la pena pelear la disputa porque el pedido fue entregado y confirmado, y el cliente no hizo reclamo previo.** — La evidencia E1 (1 fila) muestra que el pedido fue entregado y confirmado con firma, no hubo reclamo previo del cliente, no hay señales de fraude (0 señales), y el campo vale_pelear es true con decisión pelear. (evidencia: E1)

## Hipótesis descartadas

- ~~No vale la pena pelear porque hay sospecha de fraude o no existe prueba de entrega.~~ — La evidencia E1 (1 fila) muestra que esta disputa no tiene sospecha de fraude (senales_fraude = 0) y sí cuenta con prueba de entrega (firma), por lo que los motivos para no pelear no aplican. (evidencia: E1)

## Evidencia

**E1** · motor: duckdb

```sql
SELECT * FROM canonico.disputas WHERE disputa_id = 'du_cuKtmopzODI37h';
```

| disputa_id | pago_id | pedido_id | cliente_id | motivo | estado | monto | abierta_en | vence_en | nivel_riesgo | pais_facturacion | pais_ip | envio_id | transportista | region | estado_envio | prueba_entrega | tipo_destino | prometido_en | entregado_en | entrega_confirmada | entrega_tarde | extraviado | dias_atraso | zona_con_atrasos | pedidos_previos | disputas_previas | reclamo_previo | senal_cliente_nuevo | senal_riesgo_alto | senal_pais_distinto | senal_punto_retiro | senales_fraude | sospecha_fraude | causa_operativa | vale_pelear | decision | razon_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_cuKtmopzODI37h | ch_uc8Ii5EK9OUe4V | ORD-1574 | cus_3QyF0zEKBVKKDb | unrecognized | needs_response | 129.9 | 2026-09-29 15:00:00 | 2026-10-13 23:00:00 | normal | CO | CO | CS-31574 | CargoSur | Centro | entregado | firma | domicilio | 2026-09-07 | 2026-09-06 | True | False | False | 0 | False | 4 | 0 | False | False | False | False | False | 0 | False | False | True | pelear | entrega_confirmada_sin_reclamo |

**E2** · motor: duckdb

```sql
SELECT razon_decision, count(*) AS disputas FROM canonico.disputas GROUP BY razon_decision ORDER BY disputas DESC;
```

| razon_decision | disputas |
| --- | --- |
| entrega_confirmada_sin_reclamo | 20 |
| reclamo_previo | 12 |
| sin_entrega | 4 |
| sin_prueba_de_entrega | 3 |
| sospecha_de_fraude | 3 |


## Qué conviene hacer

Pelear esta disputa presentando la prueba de entrega (firma) y el historial del cliente. De las disputas totales revisadas, 20 entran en la categoría de entrega confirmada sin reclamo previo y se pueden pelear con la prueba de entrega; 12 tienen reclamo previo y es mejor resolverlas con el cliente (contactarlo, ofrecer un descuento o reembolso parcial y pedir que retire la disputa); 4 son por sin entrega y se recomienda reembolsar; 3 carecen de prueba de entrega; y 3 tienen sospecha de fraude, por lo que no se pelean y se acepta la disputa marcando al cliente.

---
Aprobación: **aprobada** · modo muestra · consultas: 2 · 8 ms
