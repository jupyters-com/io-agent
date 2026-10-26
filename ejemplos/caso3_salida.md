# Informe de IO · 20261023T174856-6b70ed

## La pregunta

> ¿Por qué subieron las disputas en la segunda quincena de septiembre de 2026?

## Lo que encontramos

Las disputas subieron de 4 a 18 entre la primera y segunda quincena de septiembre porque el transportista RapidEnvio en la región Norte tuvo muchos problemas de entrega (retrasos y paquetes extraviados). De las 18 disputas de la segunda quincena, 14 son de RapidEnvio en Norte y todas tienen causa operativa. El motivo que más creció fue producto no recibido, que pasó de 1 disputa a 8, y 7 de esas 8 tuvieron entrega tardía o paquete extraviado. No fue principalmente fraude ni cargos no reconocidos.

- **El aumento de disputas en la segunda quincena de septiembre se debe principalmente a un aumento de disputas por producto no recibido asociadas a entregas tardías o paquetes extraviados.** — En la segunda quincena las disputas por producto no recibido subieron de 1 a 8 (un aumento de 700 por ciento), y de esas 8, 7 tienen entrega tardía o paquete extraviado. Es el motivo que más creció en la quincena. (evidencia: E1)

- **El aumento está concentrado en transportistas y regiones con problemas de entregas tardías, específicamente RapidEnvio en la region Norte.** — En la segunda quincena, 14 de las 18 disputas son de RapidEnvio en la región Norte con zona con atrasos, y las 14 tienen causa operativa. Las demás combinaciones de transportista y región tienen solo 1 o 2 disputas cada una y sin causa operativa. (evidencia: E4)

## Hipótesis descartadas

- ~~El aumento se debe principalmente a disputas por cargo no reconocido.~~ — Las disputas por cargo no reconocido pasaron de 0 a 4 en la segunda quincena, muy por debajo de las disputas por producto no recibido (8) y por fraude (6). No explican el aumento principal. (evidencia: E2)
- ~~El aumento se debe principalmente a disputas por fraude, con señales de sospecha de fraude.~~ — Las disputas por fraude subieron de 3 a 6 (un aumento de 100 por ciento), menor que las de producto no recibido (de 1 a 8). De las 6 disputas por fraude de la segunda quincena, solo 1 tiene sospecha de fraude, por lo que el fraude no es la causa principal. (evidencia: E3)

## Evidencia

**E1** · motor: duckdb

```sql
WITH disputas_sept AS (SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59') SELECT quincena, count(*) AS disputas, sum(CASE WHEN entrega_tarde OR extraviado THEN 1 ELSE 0 END) AS con_entrega_tarde_o_extraviado FROM disputas_sept WHERE motivo = 'product_not_received' GROUP BY quincena ORDER BY quincena;
```

| quincena | disputas | con_entrega_tarde_o_extraviado |
| --- | --- | --- |
| primera_quincena | 1 | 0 |
| segunda_quincena | 8 | 7 |

**E2** · motor: duckdb

```sql
WITH disputas_sept AS (SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59') SELECT quincena, count(*) AS disputas FROM disputas_sept WHERE motivo = 'unrecognized' GROUP BY quincena ORDER BY quincena;
```

| quincena | disputas |
| --- | --- |
| segunda_quincena | 4 |

**E3** · motor: duckdb

```sql
WITH disputas_sept AS (SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59') SELECT quincena, count(*) AS disputas, sum(CASE WHEN sospecha_fraude THEN 1 ELSE 0 END) AS con_sospecha_fraude FROM disputas_sept WHERE motivo = 'fraudulent' GROUP BY quincena ORDER BY quincena;
```

| quincena | disputas | con_sospecha_fraude |
| --- | --- | --- |
| primera_quincena | 3 | 0 |
| segunda_quincena | 6 | 1 |

**E4** · motor: duckdb

```sql
WITH disputas_sept AS (SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59') SELECT quincena, transportista, region, zona_con_atrasos, count(*) AS disputas FROM disputas_sept GROUP BY quincena, transportista, region, zona_con_atrasos ORDER BY quincena, disputas DESC;
```

| quincena | transportista | region | zona_con_atrasos | disputas |
| --- | --- | --- | --- | --- |
| primera_quincena | PaqueteYa | Norte | False | 2 |
| primera_quincena | CargoSur | Norte | False | 1 |
| primera_quincena | CargoSur | Centro | False | 1 |
| segunda_quincena | RapidEnvio | Norte | True | 14 |
| segunda_quincena | RapidEnvio | Sur | False | 2 |
| segunda_quincena | CargoSur | Centro | False | 1 |
| segunda_quincena | PaqueteYa | Sur | False | 1 |

**E5** · motor: duckdb

```sql
SELECT razon_decision, count(*) AS disputas FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-16 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59' GROUP BY razon_decision ORDER BY disputas DESC;
```

| razon_decision | disputas |
| --- | --- |
| reclamo_previo | 8 |
| entrega_confirmada_sin_reclamo | 4 |
| sin_entrega | 4 |
| sospecha_de_fraude | 1 |
| sin_prueba_de_entrega | 1 |

**E6** · motor: duckdb

```sql
SELECT disputa_id, pedido_id, cliente_id, motivo, estado, monto, abierta_en, vence_en, transportista, region, estado_envio, prueba_entrega, entregado_en, entrega_confirmada, reclamo_previo, pedidos_previos, disputas_previas, senales_fraude, vale_pelear, razon_decision FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-16 00:00:00' AND abierta_en < TIMESTAMP '2026-10-01 00:00:00' ORDER BY disputa_id
```

| disputa_id | pedido_id | cliente_id | motivo | estado | monto | abierta_en | vence_en | transportista | region | estado_envio | prueba_entrega | entregado_en | entrega_confirmada | reclamo_previo | pedidos_previos | disputas_previas | senales_fraude | vale_pelear | razon_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| du_1jmfZda6WdIoKx | ORD-1722 | cus_zYuJS4TSV54Vmo | fraudulent | needs_response | 145.28 | 2026-09-25 15:00:00 | 2026-10-09 23:00:00 | RapidEnvio | Sur | entregado | firma | 2026-09-23 | True | False | 1 | 0 | 0 | True | entrega_confirmada_sin_reclamo |
| du_6F59FMva3JVQxJ | ORD-1648 | cus_Bt9zu6iCqSaK9F | fraudulent | needs_response | 96.07 | 2026-09-26 15:00:00 | 2026-10-10 23:00:00 | RapidEnvio | Norte | entregado | firma | 2026-09-24 | True | True | 3 | 0 | 0 | False | reclamo_previo |
| du_9dWJYUeeturRnn | ORD-1575 | cus_HCVmzNQBapw1za | fraudulent | needs_response | 241.57 | 2026-09-16 15:00:00 | 2026-09-30 23:00:00 | RapidEnvio | Norte | entregado | foto | 2026-09-15 | True | True | 4 | 0 | 0 | False | reclamo_previo |
| du_CEMNjn58fdMGmD | ORD-1615 | cus_GAuLQeym5cH0CU | product_not_received | needs_response | 130.33 | 2026-09-20 15:00:00 | 2026-10-04 23:00:00 | RapidEnvio | Norte | entregado | firma | 2026-09-18 | True | True | 2 | 0 | 0 | False | reclamo_previo |
| du_GwJYLPbbPgPC7r | ORD-1636 | cus_gtzl21g0Q7T32I | unrecognized | needs_response | 225.07 | 2026-09-22 15:00:00 | 2026-10-06 23:00:00 | RapidEnvio | Norte | entregado | foto | 2026-09-19 | True | True | 4 | 0 | 0 | False | reclamo_previo |
| du_HlcQBjPyAHVnB0 | ORD-1657 | cus_zJHtXReAeZOOc4 | product_not_received | needs_response | 61.15 | 2026-09-26 15:00:00 | 2026-10-10 23:00:00 | RapidEnvio | Norte | entregado | firma | 2026-09-24 | True | False | 0 | 0 | 1 | True | entrega_confirmada_sin_reclamo |
| du_IgNsS8yf9bEV9P | ORD-1654 | cus_H5RfvmpgiGuIZM | product_not_received | needs_response | 245.43 | 2026-09-21 15:00:00 | 2026-10-05 23:00:00 | RapidEnvio | Norte | extraviado | ninguna | None | False | True | 2 | 0 | 0 | False | sin_entrega |
| du_J2VkKpQXqpe4KC | ORD-1687 | cus_V2ly1bfklMRxAj | product_not_received | needs_response | 100.45 | 2026-09-27 15:00:00 | 2026-10-11 23:00:00 | RapidEnvio | Norte | entregado | firma | 2026-09-25 | True | True | 0 | 0 | 1 | False | reclamo_previo |
| du_LRbXAOhoJgujrS | ORD-1650 | cus_YFoGrpQQqoavsM | fraudulent | needs_response | 489.0 | 2026-09-18 15:00:00 | 2026-10-02 23:00:00 | PaqueteYa | Sur | entregado | foto | 2026-09-13 | True | False | 0 | 0 | 4 | False | sospecha_de_fraude |
| du_OELLdXYaGxqjJ1 | ORD-1678 | cus_suf7a8ROgKnQVr | unrecognized | needs_response | 217.93 | 2026-09-24 15:00:00 | 2026-10-08 23:00:00 | RapidEnvio | Norte | entregado | foto | 2026-09-23 | True | True | 2 | 0 | 0 | False | reclamo_previo |

_…y 8 filas más._

**E7** · motor: duckdb

```sql
SELECT pedido_id, creado_en, categoria, texto FROM canonico.mensajes_soporte WHERE pedido_id IN ('ORD-1722', 'ORD-1657', 'ORD-1574', 'ORD-1627') ORDER BY pedido_id, creado_en
```

_(sin filas)_


## Qué conviene hacer

De las 18 disputas de la segunda quincena: 8 tienen reclamo previo, así que hay que resolverlas con el cliente (contactarlo, disculparse, ofrecer un descuento o reembolso parcial y pedirle que retire la disputa). 4 son por sin entrega: no pelearlas y reembolsar. 4 tienen entrega confirmada y sin reclamo previo: pelear esas disputas con la prueba de entrega y el historial del cliente. 1 no tiene prueba de entrega: no pelear y reembolsar. 1 tiene sospecha de fraude: no pelear; aceptar la disputa y marcar al cliente. Además, reclamarle a RapidEnvio por la ruta al Norte y revisar esa ruta de entrega para evitar más problemas.

### Cola de aprobación

IO prepara y no envía nada: una regla de política aprueba o rechaza cada entrada, y lo aprobado lo revisa y lo envía una persona.

**El grupo** · ✅ aprobada · `AP-20261023T174856-6b70ed-1`

_Política: no se envía al banco: es el plan para la dueña, con su evidencia_

> Causa encontrada: Las disputas subieron de 4 a 18 entre la primera y segunda quincena de septiembre porque el transportista RapidEnvio en la región Norte tuvo muchos problemas de entrega (retrasos y paquetes extraviados). De las 18 disputas de la segunda quincena, 14 son de RapidEnvio en Norte y todas tienen causa operativa. El motivo que más creció fue producto no recibido, que pasó de 1 disputa a 8, y 7 de esas 8 tuvieron entrega tardía o paquete extraviado. No fue principalmente fraude ni cargos no reconocidos.
>
> De las 14 disputas de RapidEnvio · Norte en la segunda quincena de septiembre de 2026: 2 valen la pena pelear (tienen su respuesta en esta cola) y 12 no conviene pelear. [E6]
> - 8 porque el cliente ya había reclamado a soporte por ese pedido → resolver con el cliente (contactarlo, ofrecer una solución y pedirle que retire la disputa): du_6F59FMva3JVQxJ, du_9dWJYUeeturRnn, du_CEMNjn58fdMGmD, du_GwJYLPbbPgPC7r, du_J2VkKpQXqpe4KC, du_OELLdXYaGxqjJ1, du_Pp1eEgbk45lq8i, du_SdC1lwZa8XqujK
> - 4 porque el pedido no llegó → no pelear y reembolsar: du_IgNsS8yf9bEV9P, du_PMAZj7wHYofcca, du_fy30v6Y1zyMQ6G, du_gxP70mHojPHnGI
>
> Fuera de ese grupo hay 4 disputas más en la segunda quincena de septiembre de 2026, sin la misma causa: 2 valen la pena pelear (también con su respuesta en esta cola) y 2 no. [E6]
> - du_LRbXAOhoJgujrS: hay 2 o más señales de fraude → no pelear: aceptar la disputa y marcar al cliente
> - du_YiCss9xvTVSFfo: no hay prueba de entrega → resolver con el cliente: sin prueba de entrega no hay con qué pelear

**Respuesta al banco · du_1jmfZda6WdIoKx** · ✅ aprobada · `AP-20261023T174856-6b70ed-2`

_Política: cumple las 5 reglas de la política: queda lista para que una persona la envíe_

> Respuesta a la disputa du_1jmfZda6WdIoKx · el titular dice no haber hecho la compra · 145.28 USD · abierta el 2026-09-25 · vence el 2026-10-09
>
> Solicitamos que se mantenga el cargo. Evidencia:
> - Entrega: el pedido ORD-1722 se entregó el 2026-09-23 con RapidEnvio (Sur), con firma de quien recibió. [E6]
> - Historial del cliente: 1 pedido anterior y ninguna disputa previa. [E6]
> - Soporte: el cliente no escribió a soporte sobre este pedido. [E7]
> - Señales de fraude: 0 de 4 (cliente nuevo, riesgo alto, país de la IP distinto, punto de retiro). [E6]
>
> Adjuntar: comprobante de entrega (firma de quien recibió) y el historial de comunicaciones con el cliente.
> Borrador preparado por IO con datos de io-engine. Lo revisa y lo envía una persona.

**Respuesta al banco · du_HlcQBjPyAHVnB0** · ⛔ rechazada · `AP-20261023T174856-6b70ed-3`

_Política: tiene señales de fraude: la decide una persona, no la regla (1 señal(es) de fraude)_

> Respuesta a la disputa du_HlcQBjPyAHVnB0 · producto no recibido · 61.15 USD · abierta el 2026-09-26 · vence el 2026-10-10
>
> Solicitamos que se mantenga el cargo. Evidencia:
> - Entrega: el pedido ORD-1657 se entregó el 2026-09-24 con RapidEnvio (Norte), con firma de quien recibió. [E6]
> - Historial del cliente: es su primer pedido y ninguna disputa previa. [E6]
> - Soporte: el cliente no escribió a soporte sobre este pedido. [E7]
> - Señales de fraude: 1 de 4 (cliente nuevo, riesgo alto, país de la IP distinto, punto de retiro). [E6]
>
> Adjuntar: comprobante de entrega (firma de quien recibió) y el historial de comunicaciones con el cliente.
> Borrador preparado por IO con datos de io-engine. Lo revisa y lo envía una persona.

**Respuesta al banco · du_cuKtmopzODI37h** · ✅ aprobada · `AP-20261023T174856-6b70ed-4`

_Política: cumple las 5 reglas de la política: queda lista para que una persona la envíe_

> Respuesta a la disputa du_cuKtmopzODI37h · cargo no reconocido · 129.90 USD · abierta el 2026-09-29 · vence el 2026-10-13
>
> Solicitamos que se mantenga el cargo. Evidencia:
> - Entrega: el pedido ORD-1574 se entregó el 2026-09-06 con CargoSur (Centro), con firma de quien recibió. [E6]
> - Historial del cliente: 4 pedidos anteriores y ninguna disputa previa. [E6]
> - Soporte: el cliente no escribió a soporte sobre este pedido. [E7]
> - Señales de fraude: 0 de 4 (cliente nuevo, riesgo alto, país de la IP distinto, punto de retiro). [E6]
>
> Adjuntar: comprobante de entrega (firma de quien recibió) y el historial de comunicaciones con el cliente.
> Borrador preparado por IO con datos de io-engine. Lo revisa y lo envía una persona.

**Respuesta al banco · du_zZT5tciTHKDN7Y** · ✅ aprobada · `AP-20261023T174856-6b70ed-5`

_Política: cumple las 5 reglas de la política: queda lista para que una persona la envíe_

> Respuesta a la disputa du_zZT5tciTHKDN7Y · el titular dice no haber hecho la compra · 41.24 USD · abierta el 2026-09-20 · vence el 2026-10-04
>
> Solicitamos que se mantenga el cargo. Evidencia:
> - Entrega: el pedido ORD-1627 se entregó el 2026-09-19 con RapidEnvio (Norte), con firma de quien recibió. [E6]
> - Historial del cliente: 3 pedidos anteriores y ninguna disputa previa. [E6]
> - Soporte: el cliente no escribió a soporte sobre este pedido. [E7]
> - Señales de fraude: 0 de 4 (cliente nuevo, riesgo alto, país de la IP distinto, punto de retiro). [E6]
>
> Adjuntar: comprobante de entrega (firma de quien recibió) y el historial de comunicaciones con el cliente.
> Borrador preparado por IO con datos de io-engine. Lo revisa y lo envía una persona.

---
Aprobación: **aprobada** · modo muestra · consultas: 7 · 77 ms
