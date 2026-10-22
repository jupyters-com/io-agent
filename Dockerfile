# El agente de IO en modo de muestra: corre sin credenciales y sin el motor.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 SAMPLE_MODE=true
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Por defecto: el caso 3. Para otra pregunta:
#   docker run --rm io-agent python run.py '{"pregunta": "..."}'
CMD ["python", "run.py", "ejemplos/caso3_entrada.json"]
