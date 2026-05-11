# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# --- builder: install Python deps into a venv ---
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY v2/browser/requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# --- runtime: minimal image with the app + venv ---
FROM base AS runtime

RUN groupadd --system --gid 1000 app \
    && useradd --system --gid app --uid 1000 --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Only the browser subtree is needed at runtime
COPY --chown=app:app v2/browser/ /app/

# The runtime DBs live alongside the app; DATA_DIR points the app at them
ENV DATA_DIR=/app/runtime_data \
    DASH_ENABLE_SECURITY_HEADERS=1 \
    PORT=8080

USER app
EXPOSE 8080

CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:server"]
