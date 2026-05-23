FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    THERMAL_SAAS_DB_PATH=/app/storage/thermal_saas.sqlite \
    THERMAL_PDF_BROWSER_PATH=/usr/bin/chromium \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates \
        curl \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY business_profiles ./business_profiles
COPY data ./data
COPY scripts ./scripts
COPY thermal_model ./thermal_model
COPY thermal_saas ./thermal_saas
COPY utils ./utils

RUN mkdir -p /app/storage

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["sh", "-c", "uvicorn thermal_saas.api:app --host 0.0.0.0 --port ${PORT}"]
