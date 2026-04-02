# VPS Deployment Plan (Linode)

**Date**: 2026-04-02
**Status**: Not started

## Goal

Host the Plotly Dash app (`v2/browser/`) on a Linode VPS so others can access it over HTTPS. Run the orchestrator nightly via cron to keep data current.

## Server

- **Provider**: Linode (Akamai)
- **Plan**: Nanode 1GB — ~$5/month
- **OS**: Ubuntu 24.04 LTS
- **Stack**: Python 3.11 + gunicorn + nginx + Let's Encrypt

---

## One-Time Setup

### 1. Provision the server

- Create a Nanode 1GB on Linode with Ubuntu 24.04
- Add your SSH public key during provisioning
- Note the server's IP address

### 2. Initial server config

```bash
# SSH in as root, then create a non-root user
adduser oiler
usermod -aG sudo oiler

# Copy SSH key to new user
rsync --archive --chown=oiler:oiler ~/.ssh /home/oiler

# Switch to new user for remaining steps
su - oiler
```

### 3. Install dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx git
```

### 4. Clone the repo

```bash
cd /home/oiler
git clone https://github.com/<your-username>/nhl.git
cd nhl
```

### 5. Create Python virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r v2/browser/requirements.txt
pip install anthropic   # for orchestrator
```

> Add a `requirements-orchestrator.txt` if orchestrator deps grow.

### 6. Upload data

From your local machine:

```bash
# Upload 2025 data
scp -r data/2025/generated/browser/ oiler@<server-ip>:/home/oiler/nhl/data/2025/generated/browser/

# Upload 2024 data
scp -r data/2024/generated/browser/ oiler@<server-ip>:/home/oiler/nhl/data/2024/generated/browser/
```

> You can also upload the full `data/` folder if you want all raw data on the server, but only the `generated/browser/` directories are required for the app to run.

---

## Gunicorn (App Server)

### 7. Create a systemd service

Create `/etc/systemd/system/nhl.service`:

```ini
[Unit]
Description=NHL Data Browser (gunicorn)
After=network.target

[Service]
User=oiler
WorkingDirectory=/home/oiler/nhl
Environment="PATH=/home/oiler/nhl/.venv/bin"
Environment="ANTHROPIC_API_KEY=<your-key>"
ExecStart=/home/oiler/nhl/.venv/bin/gunicorn --chdir v2/browser --workers 2 --bind 127.0.0.1:8050 app:server
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable nhl
sudo systemctl start nhl
sudo systemctl status nhl
```

---

## nginx + HTTPS

### 8. Configure nginx

Create `/etc/nginx/sites-available/nhl`:

```nginx
server {
    listen 80;
    server_name <your-domain.com>;

    location / {
        proxy_pass http://127.0.0.1:8050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/nhl /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 9. Enable HTTPS with Let's Encrypt

> Requires a domain name pointed at the server's IP (set an A record at your DNS provider).

```bash
sudo certbot --nginx -d <your-domain.com>
```

Certbot auto-renews. Verify renewal timer is active:

```bash
sudo systemctl status certbot.timer
```

---

## Nightly Cron (Orchestrator)

### 10. Add cron job

```bash
crontab -e
```

Add this line (runs at 6 AM UTC daily):

```
0 6 * * * cd /home/oiler/nhl && /home/oiler/nhl/.venv/bin/python v2/orchestrator/runner.py >> /home/oiler/nhl/data/2025/logs/cron.log 2>&1
```

> Adjust the time to run a few hours after the last game of the night typically ends (games often finish by 4-5 AM UTC).

### 11. Known issue: macOS notifications

`send_notification` in the orchestrator uses macOS desktop notifications — this will fail silently on Linux. The pipeline won't crash, but the run summary won't be delivered. Options when ready:
- Replace `notify.py` with a simple email via `smtplib` or a webhook (e.g. Pushover, Slack)
- Or just rely on the cron log for now

---

## Ongoing: Updating Data

When you rebuild the db files locally and want to push them to the server:

```bash
scp data/2025/generated/browser/league.db oiler@<server-ip>:/home/oiler/nhl/data/2025/generated/browser/
scp data/2025/generated/browser/edm.db oiler@<server-ip>:/home/oiler/nhl/data/2024/generated/browser/
```

The app reads directly from SQLite — no restart needed after uploading db files.

## Ongoing: Deploying Code Changes

```bash
# On the server
cd /home/oiler/nhl
git pull
sudo systemctl restart nhl
```

---

## Cost Summary

| Item | Cost |
|------|------|
| Linode Nanode 1GB | ~$5/mo |
| Domain name | ~$10-15/yr |
| Let's Encrypt SSL | Free |
| Anthropic API (nightly Haiku runs) | ~$1-2/mo estimate |
| **Total** | ~$7-8/mo |
