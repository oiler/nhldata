# VPS Setup Guide — Plotly Dash on Fly.io

This guide covers a Plotly Dash app on Fly.io, with the SQLite database living on a Fly persistent volume. Fly handles the host, the firewall, OS patching, the reverse proxy, and TLS. You write a Dockerfile and a `fly.toml`, run `fly deploy`, and that's most of the work.

The target setup is a single `shared-cpu-1x` machine with 512MB of RAM (the smallest tier that comfortably runs Gunicorn with 2 workers) and a 1GB volume for SQLite. Total cost is roughly $4–6/month with the machine running 24/7, less if you let it auto-stop when idle.

If you'd rather self-host on a Linode VPS, see `vps-setup-guide-docker.md` for the Docker version or `vps-setup-guide.md` for a non-containerized setup.

---

## What Fly handles vs. what you still own

Fly is a managed platform, not a magic wand. Knowing the line matters.

**Fly handles:**
- Host OS, kernel patches, firewall (only ports you declare in `fly.toml` are reachable)
- TLS certificates (Let's Encrypt, auto-renewed)
- The reverse proxy in front of your app (TLS termination, HTTP/2, WebSockets)
- DDoS protection at the edge
- Volume snapshots (daily, 5 days retention by default)
- Crash restarts and health-check-based recreates

**You still own:**
- The app and its Dockerfile
- Security headers (Fly's proxy doesn't add them — they come from the app or a sidecar)
- Rate limiting per IP (Fly has concurrency limits but not per-IP throttling — see section 11)
- Off-site backups (Fly's snapshots live in the same region as the volume)
- Picking the right machine size and worker count
- Watching for SQLite corruption if you ever scale past one machine

The single-machine constraint is the biggest tradeoff. SQLite has one writer at a time, so you can't run two app instances against the same volume. If the app outgrows one machine, you switch to LiteFS (Fly's SQLite replication layer) or move to Postgres. Both are out of scope here.

---

## 1. Sign up and install flyctl

Create an account at fly.io. You'll need to add a credit card during signup — Fly bills usage-based, but the smallest setup runs a few dollars a month.

Install the CLI on your local machine:

```bash
# macOS
brew install flyctl

# Linux / WSL
curl -L https://fly.io/install.sh | sh
```

Log in:

```bash
fly auth login
```

This opens a browser for OAuth. From here on, every `fly` command runs against your account.

---

## 2. Project Files

Three files live in the repo root: `Dockerfile`, `fly.toml`, and `.dockerignore`. The `fly.toml` is Fly's equivalent of a docker-compose file — it tells Fly how to run your container, what ports to expose, what volumes to mount, and how to health-check.

Your Dash app needs to expose its underlying Flask server for Gunicorn:

```python
# app.py
from dash import Dash

app = Dash(__name__)
server = app.server  # Gunicorn entry point

# ... layout, callbacks ...

if __name__ == "__main__":
    app.run(debug=False)
```

### Dockerfile

This is the same Dockerfile from the Docker guide. Fly builds it remotely on its own builders, so you don't need Docker installed locally.

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build stage: install Python deps into a venv
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Runtime stage: minimal image, no build tools
FROM base AS runtime

RUN groupadd --system --gid 1000 app \
    && useradd --system --gid app --uid 1000 --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY --chown=app:app . .

USER app

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:server"]
```

Two changes from the Docker guide worth flagging:

- **Port 8080.** Fly's internal default is 8080. You can pick anything, but matching the convention keeps `fly.toml` simpler.
- **No `mem_limit` or `cap_drop` here.** Those settings live in `fly.toml` instead.

### requirements.txt

```
dash==2.18.1
plotly==5.24.1
gunicorn==23.0.0
flask-talisman==1.1.0
```

`flask-talisman` adds the security headers Nginx would otherwise set. More on that in section 11.

### .dockerignore

```
.git
.github
.venv
venv
__pycache__
*.pyc
.env
.env.*
*.db
*.db-journal
*.db-wal
*.db-shm
.pytest_cache
.coverage
data/
README.md
fly.toml
```

`fly.toml` lives in the repo but doesn't belong inside the image.

---

## 3. Launch the App

From the repo root:

```bash
fly launch --no-deploy
```

`fly launch` reads your repo, detects it's a Python app, and asks a series of questions:

- **App name:** Becomes part of your default URL (`your-app.fly.dev`). Has to be globally unique across Fly.
- **Region:** Pick the one closest to your users. `iad` (Virginia), `sjc` (San Jose), `lhr` (London), `ord` (Chicago) are common.
- **Postgres / Redis / Tigris / Sentry:** Say no to all of these. You're using SQLite.
- **Deploy now:** No (use `--no-deploy` above so Fly doesn't auto-deploy before the volume exists).

Fly writes a starter `fly.toml`. Replace it with the version below — the generated one is fine but doesn't include the volume mount, security limits, or auto-stop config you want.

### fly.toml

```toml
app = "your-app-name"
primary_region = "iad"

[build]

[env]
  DATABASE_PATH = "/data/app.db"
  DASH_DEBUG = "false"
  PORT = "8080"

[[mounts]]
  source = "dash_data"
  destination = "/data"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "suspend"
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

  [http_service.concurrency]
    type = "requests"
    soft_limit = 50
    hard_limit = 100

[[http_service.checks]]
  interval = "30s"
  timeout = "5s"
  grace_period = "30s"
  method = "GET"
  path = "/"

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1
```

The important details:

- **`primary_region`.** Where the machine and volume live. SQLite means you can't easily run in multiple regions, so pick one and stick with it.
- **`[[mounts]]`.** Attaches the `dash_data` volume to `/data` inside the container. Survives deploys, restarts, and machine recreates.
- **`force_https = true`.** Fly redirects all HTTP requests to HTTPS at the edge. No app-level work needed.
- **`auto_stop_machines = "suspend"`.** When idle, the machine suspends (kept-warm RAM snapshot). Wake-up takes ~1–2 seconds. Set to `"off"` for always-on at higher cost, or `"stop"` for full shutdown (cheaper but ~5–10s cold start).
- **Concurrency soft/hard limits.** When in-flight requests cross the soft limit, Fly's load balancer prefers other machines (irrelevant at one machine, but harmless). Hard limit is a backpressure signal. These are not per-IP — see section 11 for that.
- **Health check on `/`.** Fly hits this every 30 seconds. If three checks fail, Fly recreates the machine.
- **`shared-cpu-1x` / 512MB.** The smallest tier that runs 2 Gunicorn workers without thrashing. Drop to 256MB and 1 worker if cost matters more than headroom.

---

## 4. Create the Persistent Volume

Volumes are local SSDs attached to a single machine in a single region. Create one before the first deploy:

```bash
fly volumes create dash_data --region iad --size 1
```

`--size 1` is 1GB. Volumes can grow but not shrink, so start small.

Confirm:

```bash
fly volumes list
```

You should see `dash_data` with state `created`.

A note on volumes: each volume is on one host's local SSD. If that host fails, Fly's snapshot system has a daily backup, but there's a recovery gap. Section 9 covers app-level backups for the data you can't afford to lose.

---

## 5. First Deploy

```bash
fly deploy
```

Fly uploads your repo to a remote builder, builds the image, pushes it to Fly's internal registry, then starts a machine running the new image with the volume attached. The first deploy takes 2–5 minutes; subsequent ones are usually under 60 seconds thanks to layer caching.

Watch the deploy:

```bash
fly logs
```

Once it's up:

```bash
fly status
fly open
```

`fly open` opens `https://your-app-name.fly.dev` in your browser. You should see the Dash app over HTTPS, with a valid certificate, no further setup.

### If it doesn't come up

```bash
fly logs               # Recent app logs
fly status             # Machine state, health checks
fly ssh console        # Shell into the running container
```

`fly ssh console` is the equivalent of `docker exec -it container bash`. From inside, `ls /data` confirms the volume is mounted, and `ps` shows whether Gunicorn is actually running.

---

## 6. Custom Domain

You'll keep using `your-app-name.fly.dev` for free, but a real domain matters for production.

### Step 1: Add the domain to Fly

```bash
fly certs add yourdomain.com
fly certs add www.yourdomain.com
```

Fly returns the DNS records you need to create.

### Step 2: Update DNS at your registrar

For an apex domain:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `@` | (Fly's IPv4 from `fly ips list`) | 300 |
| AAAA | `@` | (Fly's IPv6 from `fly ips list`) | 300 |

For a subdomain (recommended — apex domains skip Cloudflare-style protections):

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | `app` | `your-app-name.fly.dev` | 300 |

Find your Fly app's IPs:

```bash
fly ips list
```

### Step 3: Wait for the cert

Fly issues the Let's Encrypt cert once DNS validation succeeds — usually 1–5 minutes. Watch it:

```bash
fly certs show yourdomain.com
```

When `Status: Ready` appears, your custom domain is live with HTTPS. No nginx, no certbot, no renewal cron.

---

## 7. Security Headers

The Docker guide handles this in Nginx. With Fly, there's no nginx — the headers come from the app via Flask-Talisman.

Add this near the top of `app.py`, after `server = app.server`:

```python
from flask_talisman import Talisman

CSP = {
    "default-src": "'self'",
    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'", "data:"],
    "connect-src": "'self'",
    "frame-ancestors": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}

Talisman(
    server,
    content_security_policy=CSP,
    content_security_policy_nonce_in=[],
    force_https=False,  # Fly already does this at the edge
    strict_transport_security=True,
    strict_transport_security_max_age=63072000,
    strict_transport_security_include_subdomains=True,
    referrer_policy="strict-origin-when-cross-origin",
    frame_options="DENY",
)
```

A few notes:

- **`unsafe-inline` and `unsafe-eval` are required.** Stock Plotly Dash uses both. Tightening past this needs a custom Dash setup with nonces, which most people don't bother with.
- **`force_https=False`.** Fly's edge already redirects HTTP to HTTPS. Setting this to `True` would create a double-redirect.
- **HSTS without `preload`.** Don't add preload until you've confirmed the app works for weeks. Preload is hard to undo.
- **`X-Content-Type-Options: nosniff`** and **`Permissions-Policy`** aren't set by Talisman. Add them manually:

```python
@server.after_request
def add_extra_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response
```

Deploy the change:

```bash
fly deploy
```

Verify in the browser dev tools: the response headers for the root document should include CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.

---

## 8. Rate Limiting

Fly's concurrency limits in `fly.toml` cap total in-flight requests across the machine, but they don't throttle per IP. For per-IP limiting, two reasonable options:

### Option A: flask-limiter (app-level)

```bash
# Add to requirements.txt
flask-limiter==3.8.0
```

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=lambda: request.headers.get("Fly-Client-IP", get_remote_address()),
    app=server,
    default_limits=["100 per minute"],
    storage_uri="memory://",
)
```

`Fly-Client-IP` is the header Fly's proxy injects with the real client IP. Without that, `get_remote_address()` returns Fly's internal proxy address and every request looks like the same IP.

The `memory://` storage means counters reset on machine restart and don't share across machines. Fine for a single-machine deploy. For multi-machine, point it at Redis.

### Option B: Cloudflare in front

Put your domain behind Cloudflare (free tier), then Cloudflare's rate limiting and WAF rules apply before traffic ever reaches Fly. CNAME your domain to Fly via Cloudflare instead of directly. This also gets you DDoS protection beyond what Fly's edge offers.

For a small site, app-level limiting is enough. Add Cloudflare if you start seeing real abuse.

---

## 9. Backups

Fly snapshots volumes daily and keeps 5 days by default. That's a reasonable floor, but two gaps remain: snapshots live in the same region (so a regional outage takes them out), and 5 days isn't long if you only catch a corruption a week later.

The fix is the same as the Docker guide — run a SQLite `.backup` and ship it offsite. Fly has a built-in object storage product called Tigris that's a clean fit.

### Step 1: Create a Tigris bucket

```bash
fly storage create
```

This provisions a Tigris bucket and writes the credentials as Fly secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `BUCKET_NAME`) attached to the app. Your container reads them as env vars.

### Step 2: Add a backup script

Create `backup.py` in the repo:

```python
#!/usr/bin/env python3
import os
import sqlite3
import gzip
import shutil
from datetime import datetime
from pathlib import Path
import boto3

DB_PATH = os.environ["DATABASE_PATH"]
BUCKET = os.environ["BUCKET_NAME"]
ENDPOINT = os.environ["AWS_ENDPOINT_URL_S3"]

timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
tmp_dir = Path("/tmp/backup")
tmp_dir.mkdir(exist_ok=True)
snapshot = tmp_dir / f"app-{timestamp}.db"
compressed = tmp_dir / f"app-{timestamp}.db.gz"

# Consistent snapshot — handles WAL correctly
src = sqlite3.connect(DB_PATH)
dst = sqlite3.connect(str(snapshot))
with dst:
    src.backup(dst)
src.close()
dst.close()

with open(snapshot, "rb") as f_in, gzip.open(compressed, "wb") as f_out:
    shutil.copyfileobj(f_in, f_out)

s3 = boto3.client("s3", endpoint_url=ENDPOINT)
s3.upload_file(str(compressed), BUCKET, f"backups/{compressed.name}")

snapshot.unlink()
compressed.unlink()
print(f"Uploaded {compressed.name} to {BUCKET}")
```

Add `boto3` to `requirements.txt`.

### Step 3: Schedule the backup

Fly Machines doesn't have built-in cron, but a simple loop in a separate process works. Add a `[processes]` section to `fly.toml`:

```toml
[processes]
  app = "gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 --access-logfile - --error-logfile - app:server"
  backup = "sh -c 'while true; do sleep 86400; python backup.py; done'"
```

That `backup` process runs in its own machine. To keep it on the same volume as the app, scale it to one machine in the same region:

```bash
fly deploy
fly scale count app=1 backup=1 --region iad
```

The backup machine mounts the same volume read-only via `[[mounts]]` — but Fly volumes don't support multi-attach, so the cleaner option is:

**Skip the separate process and run the backup from inside the app machine on a schedule.** Add this to `app.py`:

```python
import threading
import time
import subprocess

def backup_loop():
    while True:
        time.sleep(86400)
        try:
            subprocess.run(["python", "/app/backup.py"], check=True)
        except Exception as e:
            print(f"Backup failed: {e}")

threading.Thread(target=backup_loop, daemon=True).start()
```

Crude, but works for a single-machine setup. The backup runs once a day, in-process, and uploads to Tigris. If the app crashes, the backup thread dies with it — that's fine since Fly recreates the machine and the loop starts again.

For something more robust, move to Fly's [scheduled machines](https://fly.io/docs/machines/runtime-environment/#scheduled-machines) feature, which runs a one-shot machine on a cron expression.

### Step 4: Verify

```bash
fly ssh console
python /app/backup.py    # Run once manually
```

Then check the bucket:

```bash
fly storage list
fly storage dashboard    # Opens the Tigris UI
```

You should see `backups/app-YYYYMMDD-HHMMSS.db.gz` in the bucket.

---

## 10. Updating the App

A deploy is one command:

```bash
fly deploy
```

Fly builds a new image, starts a new machine with it, waits for health checks to pass, then routes traffic over and stops the old machine. With one machine and `auto_stop_machines = "suspend"`, there's a brief window — usually 5–15 seconds — where requests queue at the edge while the new machine boots. For most small apps, that's acceptable.

For zero-downtime, scale to two machines:

```bash
fly scale count 2
```

This breaks SQLite. Don't do it unless you've moved to LiteFS or Postgres.

### Rolling back

Every deploy is tagged. List recent versions:

```bash
fly releases
```

Roll back to a specific release:

```bash
fly releases rollback v42
```

Faster than rebuilding from a Git tag.

---

## 11. GitHub Actions Auto-Deploy

Push-to-deploy with one job and one secret.

### Step 1: Create a deploy token

```bash
fly tokens create deploy --expiry 8760h
```

That's a 1-year token scoped to deploys. Copy the entire string.

### Step 2: Store it in GitHub

Repo → **Settings → Secrets and variables → Actions** → New repository secret:

- Name: `FLY_API_TOKEN`
- Value: (paste the token)

### Step 3: Add the workflow

Save as `.github/workflows/fly-deploy.yml`:

```yaml
name: Deploy to Fly

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    concurrency: deploy-group
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

`--remote-only` builds on Fly's builders, not in the Actions runner. Faster and avoids cache misses across runs.

`concurrency: deploy-group` ensures only one deploy runs at a time — if you push twice in quick succession, the second waits for the first.

Push to main and the app deploys itself.

---

## 12. Ongoing Maintenance

Much less than a self-hosted VPS. The host, kernel, firewall, and TLS are Fly's problem. What's left is the app and its dependencies.

### Monthly checklist

- Trigger a fresh build (push a no-op commit or `gh workflow run`) to pick up Python and base image security patches
- Review Fly's status page for incidents in your region: status.flyio.net
- Check disk usage on the volume: `fly ssh console` then `df -h /data`
- Skim app logs: `fly logs --since 30d | grep -i error`
- Confirm backups in Tigris: `fly storage dashboard`
- Rotate the GitHub Actions deploy token before its expiry

### Useful commands

```bash
fly status                  # Machine state, regions, IPs
fly logs                    # Recent app logs (live tail)
fly logs --since 1h         # Last hour
fly ssh console             # Shell into the running container
fly machine list            # All machines for the app
fly machine restart MACHINE_ID
fly scale show              # Current sizing
fly releases                # Deploy history
fly volumes list            # Volume status
fly volumes snapshots list dash_data
fly certs show yourdomain.com
fly secrets list            # Env vars set as secrets
```

### Restoring from a snapshot

If the volume gets corrupted:

```bash
fly volumes snapshots list dash_data
fly volumes create dash_data_restore --snapshot-id SNAPSHOT_ID --region iad
```

That creates a new volume from the snapshot. Update `fly.toml` to mount `dash_data_restore` instead of `dash_data`, deploy, and you're running on the restored data. Once verified, destroy the old volume.

For app-level Tigris backups, pull the latest backup down and overwrite the live DB inside the container — but only after stopping Gunicorn first.

### Restart everything

```bash
fly machine restart MACHINE_ID
```

Or force a full recreate via a no-op deploy:

```bash
fly deploy --strategy immediate
```

---

## Cost Summary

For the setup in this guide, billed monthly:

| Item | Cost |
|------|------|
| `shared-cpu-1x` 512MB machine, 24/7 | ~$3.89 |
| 1GB volume | ~$0.15 |
| Bandwidth (small site, < 100GB egress) | $0 (within free allowance) |
| TLS certificates | $0 |
| Tigris bucket (a few GB of backups) | < $1 |
| **Total** | **~$5/month** |

With `auto_stop_machines = "suspend"`, the machine cost drops further during idle hours — typically 50–70% for a low-traffic dashboard. The tradeoff is the brief wake-up delay on the first request after idle.

For comparison: the Docker-on-Linode setup is $5/month flat, but you own the host hardening, patching, certbot, and backup tooling. Fly costs roughly the same and trades that work for vendor lock-in.

---

## Quick Reference

| Item | Command |
|------|---------|
| Deploy | `fly deploy` |
| Logs (live) | `fly logs` |
| Logs (last hour) | `fly logs --since 1h` |
| Shell in | `fly ssh console` |
| Status | `fly status` |
| Restart | `fly machine restart MACHINE_ID` |
| Rollback | `fly releases rollback v42` |
| Add domain | `fly certs add yourdomain.com` |
| Cert status | `fly certs show yourdomain.com` |
| List volumes | `fly volumes list` |
| Volume snapshots | `fly volumes snapshots list dash_data` |
| Scale memory | `fly scale memory 1024` |
| Scale machines | `fly scale count 1` |
| Set secret | `fly secrets set KEY=value` |
| List secrets | `fly secrets list` |
| Open in browser | `fly open` |
| Backup now | `fly ssh console -C 'python /app/backup.py'` |
