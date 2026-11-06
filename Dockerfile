FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos del proyecto
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Instalar dependencias de Python
RUN pip install --no-cache-dir \
    fastapi==0.92.0 \
    uvicorn==0.17.6 \
    pydantic==1.10.4

ENV PYTHONPATH=/app/src
ENV ENTERPRISE_DB_PATH=/app/enterprise.db
ENV PORT=8000

EXPOSE 8000

# Comando de inicio del servidor multi-agente
CMD ["sh", "-c", "python3 -m uvicorn enterprise_agents.api:app --host 0.0.0.0 --port ${PORT}"]
