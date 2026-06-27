# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    TZ=America/El_Salvador \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata libpq5 libjpeg62-turbo zlib1g libfreetype6 libopenjp2-7 libtiff6 libwebp7 liblcms2-2 libharfbuzz0b libfribidi0 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -c "import django; print(django.get_version())" \
    && python -c "import requests; print(requests.__version__)" \
    && python -c "import gunicorn; print(gunicorn.__version__)" \
    && python -c "import psycopg2; print(psycopg2.__version__)" \
    && pip check

FROM base AS runtime
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /app app \
    && mkdir -p /app/var/media /app/var/static /app/var/dte_logs \
    && chown -R app:app /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app backend/ /app/
USER app
EXPOSE 8000
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile - --error-logfile -"]
