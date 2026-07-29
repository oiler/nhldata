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

# runtime_data/2024/ and /2025/ are gitignored — they're built locally and
# baked in by tools/sync-runtime-data.sh. Any build from a bare git checkout
# (a CI runner, a fresh clone) silently produces an image whose skaters page
# raises at import, which crash-loops the machine on deploy. Fail the *build*
# instead, before the image is ever pushed.
RUN set -eu; \
    fail=0; \
    for f in runtime_data/2024/league.db \
             runtime_data/2025/league.db \
             runtime_data/2025/edm.db \
             runtime_data/2025/player_bursts.csv \
             runtime_data/goalies.db; do \
        if [ ! -s "/app/$f" ]; then \
            echo "ERROR: runtime data missing or empty: $f" >&2; \
            fail=1; \
        fi; \
    done; \
    if [ "$fail" -ne 0 ]; then \
        echo "Run ./tools/sync-runtime-data.sh from the repo root, then deploy." >&2; \
        exit 1; \
    fi

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
