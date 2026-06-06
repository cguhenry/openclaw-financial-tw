# Docker Host Deployment

Use this profile when you have a normal Linux box, mini PC, NUC, or VPS with Docker Compose.

## 1. Prepare

```bash
git clone https://github.com/cguhenry/openclaw-financial-tw.git
cd openclaw-financial-tw
cp .env.example .env
```

Fill at least:

- `FINMIND_TOKEN`
- `FUGLE_API_KEY` if you want better realtime fallback
- `DASHBOARD_CORS_ORIGINS` with your real web origin
- `DASHBOARD_ALERT_PREVIEW_TTL_SECONDS` if you want to tune preview freshness vs. latency

## 2. Start dashboard stack

```bash
docker compose --profile dashboard up -d --build
```

## 3. Verify

```bash
curl http://127.0.0.1:9180/api/health
curl -I http://127.0.0.1:9123/sse
```

Open:

- Web: `http://HOST_IP:9080`
- API: `http://HOST_IP:9180/api/health`

## 4. Optional notifications

If the container does not have `openclaw` CLI, alert hits still appear in the in-app alert center and the outbox file:

- `./data/dashboard-alerts.json`
- `./data/dashboard-notification-outbox.jsonl`

External Discord/LINE/Telegram delivery is best supported when the API runs in a host environment that already has `openclaw` installed.
