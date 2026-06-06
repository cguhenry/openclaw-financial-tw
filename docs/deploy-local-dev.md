# Local Development Deployment

Use this path for macOS, Linux, or Windows development.

## 1. API

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r dashboard/api/requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn dashboard.api.app.main:app --host 127.0.0.1 --port 9180 --reload
```

## 2. Web

```bash
cd dashboard/web
npm install --include=dev
npm run dev
```

## 3. Verify

- Web: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:9180/api/health`
- Dashboard alerts poll in the background every `DASHBOARD_ALERT_POLL_INTERVAL_SECONDS`
- AI alert preview cache TTL is controlled by `DASHBOARD_ALERT_PREVIEW_TTL_SECONDS`

## 4. Local files

By default the dashboard writes:

- `./data/dashboard-alerts.json`
- `./data/dashboard-notification-outbox.jsonl`
- trained models under `dashboard/api/models/`
