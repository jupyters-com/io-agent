# Informe de IO · 20261023T143418-ebb3e0

## La pregunta

> ¿Por qué subieron las disputas en la segunda quincena de septiembre de 2026?

## Lo que encontramos

Las disputas subieron de 4 a 18 entre la primera y segunda quincena de septiembre porque el transportista RapidEnvio en la región Norte tuvo muchos problemas de entrega (retrasos y paquetes extraviados). De las 18 disputas de la segunda quincena, 14 son de RapidEnvio en Norte y todas tienen causa operativa. El motivo que más creció fue producto no recibido, que pasó de 1 disputa a 8, y 7 de esas 8 tuvieron entrega tardía o paquete extraviado. No fue principalmente fraude ni cargos no reconocidos.

- **El aumento de disputas en la segunda quincena de septiembre se debe principalmente a disputas por producto no recibido (product_not_received) vinculadas a entregas tardías o extraviadas.** — En la segunda quincena las disputas product_not_received subieron de 1 a 8 (700% de aumento), y de esas 8, 7 tienen entrega_tarde o extraviado, y 7 están en zona con atrasos. Es el motivo que más creció en la quincena (pasó de 1 de 4 disputas a 8 de 18). (evidencia: E1, E4)

- **El aumento está concentrado en transportistas y regiones con zona con atrasos, es decir, un problema operativo de entregas.** — En la segunda quincena, 14 de las 18 disputas son de RapidEnvio en la región Norte con zona con atrasos, y las 14 tienen causa_operativa. Las demás combinaciones de transportista y región tienen solo 1 o 2 disputas cada una y sin causa operativa. (evidencia: E4)

## Hipótesis descartadas

- ~~El aumento se debe principalmente a disputas por fraude (fraudulent) con señales como cliente nuevo, riesgo alto, país IP distinto o punto de retiro.~~ — Las disputas fraudulentas subieron de 3 a 6 (100% de aumento), un incremento menor que el de product_not_received (de 1 a 8). De las 6 disputas fraudulentas de la segunda quincena, solo 1 tiene sospecha_fraude y el total de señales de fraude es 4, por lo que el fraude no es la causa principal. (evidencia: E2)
- ~~El aumento se debe principalmente a disputas por cargo no reconocido (unrecognized).~~ — Las disputas unrecognized pasaron de 0 a 4 en la segunda quincena, muy por debajo de product_not_received (8) y fraudulent (6). No explican el aumento principal. (evidencia: E3)

## Evidencia

**E1** · motor: duckdb

```sql
WITH d AS ( SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59' ) SELECT quincena, count(*) AS total_disputas, sum(CASE WHEN motivo='product_not_received' THEN 1 ELSE 0 END) AS pnr_disputas, sum(CASE WHEN motivo='product_not_received' AND (entrega_tarde OR extraviado) THEN 1 ELSE 0 END) AS pnr_con_problema_entrega, sum(CASE WHEN motivo='product_not_received' AND zona_con_atrasos THEN 1 ELSE 0 END) AS pnr_zona_atrasos FROM d GROUP BY quincena ORDER BY quincena;
```

| quincena | total_disputas | pnr_disputas | pnr_con_problema_entrega | pnr_zona_atrasos |
| --- | --- | --- | --- | --- |
| primera_quincena | 4 | 1 | 0 | 0 |
| segunda_quincena | 18 | 8 | 7 | 7 |

**E2** · motor: duckdb

```sql
WITH d AS ( SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59' ) SELECT quincena, count(*) AS total_disputas, sum(CASE WHEN motivo='fraudulent' THEN 1 ELSE 0 END) AS fraude_disputas, sum(CASE WHEN motivo='fraudulent' AND sospecha_fraude THEN 1 ELSE 0 END) AS fraude_con_sospecha, sum(CASE WHEN motivo='fraudulent' THEN senales_fraude ELSE 0 END) AS senales_fraude_total FROM d GROUP BY quincena ORDER BY quincena;
```

| quincena | total_disputas | fraude_disputas | fraude_con_sospecha | senales_fraude_total |
| --- | --- | --- | --- | --- |
| primera_quincena | 4 | 3 | 0 | 2 |
| segunda_quincena | 18 | 6 | 1 | 4 |

**E3** · motor: duckdb

```sql
WITH d AS ( SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59' ) SELECT quincena, count(*) AS total_disputas, sum(CASE WHEN motivo='unrecognized' THEN 1 ELSE 0 END) AS unrecognized_disputas FROM d GROUP BY quincena ORDER BY quincena;
```

| quincena | total_disputas | unrecognized_disputas |
| --- | --- | --- |
| primera_quincena | 4 | 0 |
| segunda_quincena | 18 | 4 |

**E4** · motor: duckdb

```sql
WITH d AS ( SELECT *, CASE WHEN abierta_en >= TIMESTAMP '2026-09-16 00:00:00' THEN 'segunda_quincena' ELSE 'primera_quincena' END AS quincena FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-01 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59' ) SELECT quincena, transportista, region, zona_con_atrasos, count(*) AS disputas, sum(CASE WHEN causa_operativa THEN 1 ELSE 0 END) AS con_causa_operativa FROM d GROUP BY quincena, transportista, region, zona_con_atrasos ORDER BY quincena, disputas DESC;
```

| quincena | transportista | region | zona_con_atrasos | disputas | con_causa_operativa |
| --- | --- | --- | --- | --- | --- |
| primera_quincena | PaqueteYa | Norte | False | 2 | 0 |
| primera_quincena | CargoSur | Norte | False | 1 | 0 |
| primera_quincena | CargoSur | Centro | False | 1 | 0 |
| segunda_quincena | RapidEnvio | Norte | True | 14 | 14 |
| segunda_quincena | RapidEnvio | Sur | False | 2 | 0 |
| segunda_quincena | PaqueteYa | Sur | False | 1 | 0 |
| segunda_quincena | CargoSur | Centro | False | 1 | 0 |

**E5** · motor: duckdb

```sql
WITH d AS ( SELECT * FROM canonico.disputas WHERE abierta_en >= TIMESTAMP '2026-09-16 00:00:00' AND abierta_en <= TIMESTAMP '2026-09-30 23:59:59' ) SELECT razon_decision, count(*) AS disputas FROM d GROUP BY razon_decision ORDER BY disputas DESC;
```

| razon_decision | disputas |
| --- | --- |
| reclamo_previo | 8 |
| sin_entrega | 4 |
| entrega_confirmada_sin_reclamo | 4 |
| sin_prueba_de_entrega | 1 |
| sospecha_de_fraude | 1 |


## Qué conviene hacer

De las 18 disputas de la segunda quincena: 8 tienen reclamo previo, así que hay que resolverlas con el cliente (contactarlo, disculparse, ofrecer un descuento o reembolso parcial y pedirle que retire la disputa). 4 son por sin entrega: no pelearlas y reembolsar. 4 tienen entrega confirmada y sin reclamo previo: pelear esas disputas con la prueba de entrega y el historial del cliente. 1 no tiene prueba de entrega: no pelear y reembolsar. 1 tiene sospecha de fraude: no pelear; aceptar la disputa y marcar al cliente. Además, reclamarle a RapidEnvio por la ruta al Norte y revisar esa ruta de entrega para evitar más problemas.

---
Aprobación: **aprobada** · modo muestra · consultas: 5 · 9 ms
