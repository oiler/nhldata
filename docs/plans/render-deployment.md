# Render Deployment Plan

**Date**: 2026-03-30
**Status**: Not started — paused to resume later

claude --resume c765643a-acd1-443e-9d8e-5b6228e47f77

## Goal

Host the Plotly Dash app (`v2/browser/`) on Render so others can access it. Low traffic for now, needs to be secure (HTTPS).

## Account

- Render account already created.

## Key Constraints

- App uses SQLite databases (`edm.db`, `league.db`) stored in `data/` which is gitignored
- Repo is **public** on GitHub — do not commit large binary db files to it
- Active development is happening on `master` — don't disrupt it
- gunicorn is already in `requirements.txt` and `app.server` is exposed

## Database File Sizes

| File | Size |
|------|------|
| `data/2025/generated/browser/edm.db` | 33 MB |
| `data/2025/generated/browser/league.db` | 5.6 MB |
| `data/2024/generated/browser/league.db` | 5.0 MB |

## Agreed Approach

1. **Do not commit db files to the public repo** — use Render's persistent disk instead (~$0.25/GB/month, ~free for 40 MB)
2. **Create a `render` branch** off current master for deployment config — avoids colliding with active master work
3. Once other session's work is merged, rebase `render` onto it

## Steps to Complete

### 1. Create `render` branch
```bash
git checkout -b render
```

### 2. Add `Procfile`
Create `Procfile` at repo root:
```
web: gunicorn --chdir v2/browser app:server
```

### 3. Add `.python-version`
Create `.python-version` at repo root:
```
3.11.6
```

### 4. Push branch to GitHub
```bash
git push -u origin render
```

### 5. Create Render Web Service
- Connect GitHub repo
- Branch: `render`
- Root directory: (repo root)
- Build command: `pip install -r v2/browser/requirements.txt`
- Start command: pulled from `Procfile` automatically
- Set env var: `PYTHON_VERSION=3.11.6`

### 6. Add Persistent Disk
- In the Render service dashboard → Disks
- Mount path: `/opt/render/project/src/data`
- Size: 1 GB (minimum, costs ~$0.25/mo)

### 7. Upload db files
Use Render's shell (in dashboard) to confirm the mount path, then upload db files:
```bash
# From local machine
scp data/2025/generated/browser/edm.db <render-ssh-target>:/opt/render/project/src/data/2025/generated/browser/
# repeat for league.db files
```
> Note: Verify Render's SSH/shell access method in their dashboard — it may use their web shell rather than direct SSH.

### 8. Verify deploy
- Check app loads at the Render-provided `.onrender.com` URL
- Render provides HTTPS automatically on all deployments

## Notes

- Render auto-provisions TLS/HTTPS — nothing to configure for security
- When db files are rebuilt locally, re-upload to the persistent disk via Render shell
- The `render` branch only needs `Procfile` and `.python-version` — all app code comes from master via rebase
