# Informe de IO · 20261022T144235-54fd7b

## La pregunta

> ¿Vale la pena pelear la disputa du_cuKtmopzODI37h?

## Lo que encontramos

**IO no da una conclusión.** El investigador todavía no está implementado (Paso 10): IO puede ver el panorama de las disputas, pero aún no prueba hipótesis, así que prefiere no concluir.

## Hipótesis descartadas

_Ninguna en esta corrida._

## Evidencia

**E1** · motor: duckdb

```sql
SELECT motivo, count(*) AS disputas, sum(CASE WHEN decision = 'pelear' THEN 1 ELSE 0 END) AS vale_pelear FROM canonico.disputas GROUP BY motivo ORDER BY disputas DESC, motivo
```

| motivo | disputas | vale_pelear |
| --- | --- | --- |
| fraudulent | 16 | 8 |
| product_not_received | 16 | 6 |
| unrecognized | 10 | 6 |


## Qué conviene hacer

_Sin recomendación: no hay conclusión._

---
Aprobación: **aprobada** · modo muestra · consultas: 1 · 1 ms
