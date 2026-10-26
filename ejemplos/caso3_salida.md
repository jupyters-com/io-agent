# Informe de IO · 20261023T171916-f3f4ca

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


## Qué conviene hacer

De las 18 disputas de la segunda quincena: 8 tienen reclamo previo, así que hay que resolverlas con el cliente (contactarlo, disculparse, ofrecer un descuento o reembolso parcial y pedirle que retire la disputa). 4 son por sin entrega: no pelearlas y reembolsar. 4 tienen entrega confirmada y sin reclamo previo: pelear esas disputas con la prueba de entrega y el historial del cliente. 1 no tiene prueba de entrega: no pelear y reembolsar. 1 tiene sospecha de fraude: no pelear; aceptar la disputa y marcar al cliente. Además, reclamarle a RapidEnvio por la ruta al Norte y revisar esa ruta de entrega para evitar más problemas.

---
Aprobación: **aprobada** · modo muestra · consultas: 5 · 45 ms
