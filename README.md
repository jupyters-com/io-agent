# io-agent · el agente de IO para contracargos

Agente que investiga por qué suben las disputas de pago: propone explicaciones, las prueba con datos y descarta las que la evidencia no sostiene, dejando anotada cada prueba.

Construido durante el Open Agent Hackathon 2026 (Track 02 · The Agent That Can Explain Why), desde el 22-oct-2026.

## De dónde salen los datos

El agente no lee bases ni archivos directamente. Le pregunta al motor **io-engine**, que se declara como **componente previo** (construido antes del 22-oct-2026 00:00 UTC, tag `previo-22oct`). El motor se levanta aparte con `docker compose up --build` y expone la herramienta `consultar(sql)` por MCP en `http://localhost:8000/mcp`.

Todo lo que está en este repo es trabajo nuevo del hackathon.

## Estado

En construcción.

## License

PolyForm Noncommercial 1.0.0 · ver `LICENSE`.