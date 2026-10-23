# La misma pregunta, con y sin la capa de IO

Mismo modelo, misma pregunta, mismos datos. **Con capa:** el esquema canónico de io-engine, sus definiciones y Meterless (H-MEM y World Model). **Sin capa** (`SEMANTIC_LAYER=off`): las tablas crudas tal como llegan de pagos, logística y soporte, sin definiciones ni Meterless. Las salidas salen de corridas reales (`python scripts/comparar_capa.py`), nunca escritas a mano.

## caso1

> ¿Vale la pena pelear la disputa du_cuKtmopzODI37h?

| | Con la capa de IO | Sin la capa |
| --- | --- | --- |
| **Estado** | concluida | concluida |
| **Conclusión** | Sí, vale la pena pelear la disputa du_cuKtmopzODI37h, por 129.9 dólares. El pedido fue entregado y confirmado con firma, el cliente no había reclamado antes y no hay indicios de fraude. Cumple todas las condiciones para ganarla. | No vale la pena pelear la disputa du_cuKtmopzODI37h de 129,90 dólares. No existe prueba de entrega del pedido: el estado del envío, la prueba de entrega y la fecha de entrega están vacíos, por lo que no hay evidencia que presentar para defender el cobro. |
| **Hipótesis** | ✔ Vale la pena pelear la disputa du_cuKtmopzODI37h porque el pedido fue entregado y confirmado, y el cliente no hizo un reclamo previo.<br>✘ No vale la pena pelear la disputa du_cuKtmopzODI37h porque hay sospecha de fraude en este caso.<br>✘ No vale la pena pelear la disputa du_cuKtmopzODI37h porque el pedido no llegó o no hay prueba de entrega.<br>✘ No vale la pena pelear la disputa du_cuKtmopzODI37h porque el cliente ya había hecho un reclamo previo sobre este pedido. | ✘ Vale la pena pelear la disputa du_cuKtmopzODI37h porque el pedido fue entregado y confirmado, y el cliente no hizo un reclamo previo.<br>✘ No vale la pena pelear la disputa du_cuKtmopzODI37h porque hay sospecha de fraude en este caso.<br>✘ No vale la pena pelear la disputa du_cuKtmopzODI37h porque el cliente ya había hecho un reclamo previo sobre este pedido.<br>✔ No vale la pena pelear la disputa du_cuKtmopzODI37h porque no hay prueba de entrega o el envío no llegó. |
| **Qué conviene hacer** | Pelear la disputa presentando la prueba de entrega (firma) y el historial del cliente. Como es una sola disputa con entrega confirmada y sin reclamo previo, se recomienda pelearla en lugar de reembolsar o contactar al cliente. | Aceptar esta disputa y no destinar recursos a combatirla, dado que no hay evidencia de entrega que presentar. |
| **Consultas (fallidas)** | 6 (0) | 4 (0) |
| **Vueltas · devoluciones** | 2 · 0 | 2 · 0 |
| **Cola de aprobación** | respuesta_banco du_cuKtmopzODI37h: aprobada | — |
| **Traza** | `logs/20261023T190852-cc9da2.jsonl` | `logs/20261023T190852-8ea40e.jsonl` |

## caso2

> ¿Vale la pena pelear la disputa du_LRbXAOhoJgujrS?

| | Con la capa de IO | Sin la capa |
| --- | --- | --- |
| **Estado** | concluida | concluida |
| **Conclusión** | No, no vale la pena pelear la disputa du_LRbXAOhoJgujrS de 489 dólares. El pedido llegó y hay una foto como prueba de entrega, y el cliente no había hecho un reclamo previo sobre este pedido. Sin embargo, se detectaron 4 señales de fraude y el cliente está bajo sospecha de fraude, por lo que no se debe pelear. | No vale la pena pelear la disputa du_LRbXAOhoJgujrS de 489 dólares. Está marcada como fraude con riesgo máximo, hay una diferencia entre el país de facturación y el país de la dirección IP, y no existe prueba de entrega del pedido. |
| **Hipótesis** | ✘ Vale la pena pelear la disputa du_LRbXAOhoJgujrS porque el pedido fue entregado y confirmado, y el cliente no hizo un reclamo previo sobre este pedido.<br>✔ No vale la pena pelear la disputa du_LRbXAOhoJgujrS porque el cliente está bajo sospecha de fraude. | ✘ Vale la pena pelear la disputa du_LRbXAOhoJgujrS porque el pedido fue entregado y confirmado, y el cliente no hizo un reclamo previo.<br>✔ No vale la pena pelear la disputa du_LRbXAOhoJgujrS porque hay sospecha de fraude en este caso.<br>✘ No vale la pena pelear la disputa du_LRbXAOhoJgujrS porque el cliente ya había hecho un reclamo previo sobre este pedido.<br>✔ No vale la pena pelear la disputa du_LRbXAOhoJgujrS porque no hay prueba de entrega o el envío no llegó. |
| **Qué conviene hacer** | No pelear esta disputa; aceptarla y marcar al cliente por sospecha de fraude. De las 1 disputas del grupo, 1 se debe aceptar por sospecha de fraude y marcar al cliente. | Aceptar esta disputa y no destinar recursos a combatirla. Marcar al cliente por sospecha de fraude. |
| **Consultas (fallidas)** | 5 (0) | 4 (0) |
| **Vueltas · devoluciones** | 4 · 2 | 2 · 0 |
| **Cola de aprobación** | no_pelear du_LRbXAOhoJgujrS: aprobada | — |
| **Traza** | `logs/20261023T190852-97f09a.jsonl` | `logs/20261023T190852-adf5f1.jsonl` |

## caso3

> ¿Por qué subieron las disputas en la segunda quincena de septiembre de 2026?

| | Con la capa de IO | Sin la capa |
| --- | --- | --- |
| **Estado** | concluida | concluida |
| **Conclusión** | Las disputas subieron de 4 a 18 entre la primera y segunda quincena de septiembre porque el transportista RapidEnvio en la región Norte tuvo muchos problemas de entrega (retrasos y paquetes extraviados). De las 18 disputas de la segunda quincena, 14 son de RapidEnvio en Norte y todas tienen causa operativa. El motivo que más creció fue producto no recibido, que pasó de 1 disputa a 8, y 7 de esas 8 tuvieron entrega tardía o paquete extraviado. No fue principalmente fraude ni cargos no reconocidos. | El aumento de disputas en la segunda quincena de septiembre (de 5 a 28 disputas) se debe principalmente a problemas de producto y entrega: 8 disputas por producto no recibido contra solo 1 en la primera quincena, y un fuerte incremento en tickets de producto dañado. No hay evidencia de fraude organizado como causa principal. |
| **Hipótesis** | ✔ El aumento de disputas en la segunda quincena de septiembre se debe principalmente a un aumento de disputas por producto no recibido asociadas a entregas tardías o paquetes extraviados.<br>✘ El aumento se debe principalmente a disputas por cargo no reconocido.<br>✘ El aumento se debe principalmente a disputas por fraude, con señales de sospecha de fraude.<br>✔ El aumento está concentrado en transportistas y regiones con problemas de entregas tardías, específicamente RapidEnvio en la region Norte. | ✔ El aumento de disputas en la segunda quincena de septiembre se debe principalmente a clientes que reclaman que no recibieron el producto, ligado a entregas tardías o extraviadas.<br>✘ El aumento se debe principalmente a disputas por fraude, con señales como cliente nuevo, riesgo alto, país de IP distinto al de facturación o envío a punto de retiro.<br>✔ El aumento se debe principalmente a disputas por cargo no reconocido, es decir, el cliente no reconoce el cargo.<br>✔ El aumento está concentrado en transportistas y regiones con problemas de entregas tardías, es decir, un problema operativo de envíos. |
| **Qué conviene hacer** | De las 18 disputas de la segunda quincena: 8 tienen reclamo previo, así que hay que resolverlas con el cliente (contactarlo, disculparse, ofrecer un descuento o reembolso parcial y pedirle que retire la disputa). 4 son por sin entrega: no pelearlas y reembolsar. 4 tienen entrega confirmada y sin reclamo previo: pelear esas disputas con la prueba de entrega y el historial del cliente. 1 no tiene prueba de entrega: no pelear y reembolsar. 1 tiene sospecha de fraude: no pelear; aceptar la disputa y marcar al cliente. Además, reclamarle a RapidEnvio por la ruta al Norte y revisar esa ruta de entrega para evitar más problemas. | Priorizar la defensa de las 8 disputas por producto no recibido, evaluar caso a caso las 4 de cargo no reconocido y las 6 de fraude, y reforzar el seguimiento de envíos y la comunicación proactiva con los clientes para reducir quejas de producto dañado y ubicación del pedido. |
| **Consultas (fallidas)** | 7 (0) | 10 (2) |
| **Vueltas · devoluciones** | 5 · 0 | 13 · 2 |
| **Cola de aprobación** | grupo: aprobada<br>respuesta_banco du_1jmfZda6WdIoKx: aprobada<br>respuesta_banco du_HlcQBjPyAHVnB0: rechazada<br>respuesta_banco du_cuKtmopzODI37h: aprobada<br>respuesta_banco du_zZT5tciTHKDN7Y: aprobada | — |
| **Traza** | `logs/20261023T190852-d8ae95.jsonl` | `logs/20261023T190852-898782.jsonl` |

