# Informe de IO · 20261022T194850-cc4c74

## La pregunta

> ¿Vale la pena pelear la disputa du_cuKtmopzODI37h?

## Lo que encontramos

**IO no da una conclusión.** No hay una corrida grabada (o se terminó) para esta pregunta en modo de muestra.

## Hipótesis descartadas

_Ninguna en esta corrida._

## Evidencia

**E1** · motor: duckdb

```sql
SELECT disputa_id, monto, motivo, estado, abierta_en, vence_en, nivel_riesgo, pais_facturacion, pais_ip, envio_id, transportista, region, estado_envio, prueba_entrega, tipo_destino, prometido_en, entregado_en, entrega_confirmada, entrega_tarde, extraviado, dias_atraso, zona_con_atrasos, pedidos_previos, disputas_previas, reclamo_previo, senal_cliente_nuevo, senal_riesgo_alto, senal_pais_distinto, senal_punto_retiro, senales_fraude, sospecha_fraude, causa_operativa, vale_pelear, decision, razon_decision FROM canonico.disputas WHERE disputa_id = 'du_cuKtmopzODI37h';
```

| disputa_id | monto | motivo | estado | abierta_en | vence_en | nivel_riesgo | pais_facturacion | pais_ip | envio_id | transportista | region | estado_envio | prueba_entrega | tipo_destino | prometido_en | entregado_en | entrega_confirmada | entrega_tarde | extraviado | dias_atraso | zona_con_atrasos | pedidos_previos | disputas_previas | reclamo_previo | senal_cliente_nuevo | senal_riesgo_alto | senal_pais_distinto | senal_punto_retiro | senales_fraude | sospecha_fraude | causa_operativa | vale_pelear | decision | razon_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_cuKtmopzODI37h | 129.9 | unrecognized | needs_response | 2026-09-29 15:00:00 | 2026-10-13 23:00:00 | normal | CO | CO | CS-31574 | CargoSur | Centro | entregado | firma | domicilio | 2026-09-07 | 2026-09-06 | True | False | False | 0 | False | 4 | 0 | False | False | False | False | False | 0 | False | False | True | pelear | entrega_confirmada_sin_reclamo |


## Qué conviene hacer

_Sin recomendación: no hay conclusión._

---
Aprobación: **aprobada** · modo muestra · consultas: 1 · 6 ms
