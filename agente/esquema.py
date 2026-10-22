"""Lo que el modelo sabe de los datos: las 5 tablas de la capa canónica de io-engine.

Es la "capa semántica" vista desde el agente. Viene de dbt_io/models/canonico (io-engine);
si allá cambia una columna o una regla, se cambia aquí.
"""

ESQUEMA = """
Esquema `canonico` (5 tablas; mismas columnas en DuckDB y en Zetaris):

canonico.clientes — un cliente por fila
  cliente_id, correo, creado_en, primer_pago_en, pagos_totales

canonico.pagos — un cobro por pedido
  pago_id, pedido_id, cliente_id, monto (USD), moneda, pagado_en, pais_facturacion, pais_ip,
  nivel_riesgo ('normal' | 'elevated' | 'highest'), tarjeta_ultimos4

canonico.envios — un envío por pedido
  envio_id, pedido_id, transportista, region, despachado_en, prometido_en, entregado_en (NULL si no llegó),
  estado ('entregado' | 'en_transito' | 'extraviado' | 'devuelto'), prueba_entrega ('firma' | 'foto' | 'ninguna'),
  tipo_destino ('domicilio' | 'punto_retiro'),
  entrega_confirmada, extraviado, entrega_tarde, dias_atraso, envios_zona, tasa_tarde_zona, zona_con_atrasos

canonico.mensajes_soporte — un mensaje de soporte por fila
  mensaje_id, cliente_id, pedido_id, creado_en, categoria, texto, estado

canonico.disputas — una disputa por fila, con su contexto ya unido
  disputa_id, pago_id, pedido_id, cliente_id, motivo ('fraudulent' | 'product_not_received' | 'unrecognized'),
  estado, monto, abierta_en, vence_en, nivel_riesgo, pais_facturacion, pais_ip,
  envio_id, transportista, region, estado_envio, prueba_entrega, tipo_destino, prometido_en, entregado_en,
  entrega_confirmada, entrega_tarde, extraviado, dias_atraso, zona_con_atrasos,
  pedidos_previos, disputas_previas, reclamo_previo,
  senal_cliente_nuevo, senal_riesgo_alto, senal_pais_distinto, senal_punto_retiro, senales_fraude,
  sospecha_fraude, causa_operativa, vale_pelear, decision ('pelear' | 'no_pelear'), razon_decision

Definiciones (escritas una sola vez en io-engine):
- entrega_confirmada: estado 'entregado' Y prueba de entrega firma o foto.
- entrega_tarde: entregado después de prometido_en, o sin entregar más de 3 días después (corte 2026-09-30).
- zona_con_atrasos: en ±7 días, el mismo transportista y región entregó tarde al menos el 50 % de sus envíos.
- reclamo_previo: hay un mensaje de soporte del mismo cliente sobre el mismo pedido ANTES de abrir la disputa.
- senales_fraude (suman 1 cada una): cliente sin pedidos previos, nivel_riesgo 'highest', pais_ip distinto
  de pais_facturacion, envío a punto de retiro. 2 o más = sospecha_fraude.
- vale_pelear: entrega confirmada Y sin reclamo previo Y menos de 2 señales de fraude.
- causa_operativa: entrega tarde o extraviada Y su transportista/región está en zona con atrasos.
- razon_decision: sin_entrega · sospecha_de_fraude · sin_prueba_de_entrega · reclamo_previo ·
  entrega_confirmada_sin_reclamo.

Datos: julio a septiembre de 2026. Fechas en UTC.
SQL: una sola sentencia SELECT por consulta (se permite WITH), máximo 100 filas. Usa SQL estándar que funcione
en DuckDB y en Spark: CASE WHEN, count, sum, GROUP BY, JOIN; fechas como TIMESTAMP '2026-09-16 00:00:00'.
Evita subconsultas correlacionadas y funciones propias de un solo motor.
"""
