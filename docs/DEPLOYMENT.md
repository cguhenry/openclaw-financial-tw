# OpenClaw Financial TW Deployment

This document covers the production-ish deployment shape that exists in this repository today.

## What This Project Is

This project runs as:

1. An OpenClaw skill layer under `/home/node/.openclaw/workspace/skills/tw-*`
2. A Taiwan financial MCP server in [mcp/finmind_server.py](/home/node/.openclaw/workspace/projects/openclaw-financial-tw/mcp/finmind_server.py)
3. Optional automation scripts in [scripts/](/home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts)

Docker is a deployment wrapper for the MCP server. It is not a separate product architecture.

## Deployment Modes

### Mode A: Local OpenClaw Workspace

Use this when OpenClaw already runs on the same machine.

Requirements:

- Python virtualenv at `projects/openclaw-financial-tw/.venv`
- Valid `.env` with `FINMIND_TOKEN`
- Optional `FUGLE_API_KEY` for realtime quote fallback

Start the local SSE server:

```bash
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/run_finmind_sse.sh
```

Keep it healthy:

```bash
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/ensure_finmind_sse.sh
```

Verify:

```bash
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_sse.py
```

> **First-time setup**: if `finmind` imports fail with `ModuleNotFoundError: No module named 'tqdm'`, install it manually:
> ```bash
> /home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/pip install tqdm python-dotenv
> ```
> (These should be in `requirements.txt` but may be missed on first install.)

### Mode B: Docker Compose

Use this when you want the MCP server isolated from the main OpenClaw Python environment.

> **Important**: The `requirements.txt` is the source of truth for all Python packages installed inside the container. If you edit it (e.g. after updating packages), you must **rebuild** the container for changes to take effect:
> ```bash
> docker compose up -d --build
> ```
> Rebuild causes ~2–3 minutes of SSE downtime.

```bash
cd /home/node/.openclaw/workspace/projects/openclaw-financial-tw
cp .env.example .env
# fill FINMIND_TOKEN and optional values
docker compose up -d --build
```

Health check:

```bash
docker compose ps
docker compose logs --tail=100 finmind-tw-mcp
```

Verify container has all required packages:

```bash
docker exec finmind-tw-mcp pip list | grep -E "tqdm|finmind|mcp|uvicorn"
# Expected: tqdm, finmind, mcp, uvicorn all listed
```

If `tqdm` or other packages are missing, rebuild the container (they may come from transitive dependencies of `finmind` that are not always auto-installed):

```bash
docker compose up -d --build
```

The container exposes:

- `http://127.0.0.1:9123/sse`
- `http://127.0.0.1:9123/mcp`

### Multi-Client / LAN Access (Mode B)

By default the MCP server inside the Docker container binds to `127.0.0.1`, so only processes on the **same machine** can reach it. If you want other OpenClaw instances on the same LAN to connect to this container, two changes are required:

**1. Bind the MCP server to all network interfaces**

In your `.env` (not `.env.example`), set:

```dotenv
MCP_HOST=0.0.0.0
```

This tells the MCP server to listen on every network interface, not just localhost.

**2. Point each client OpenClaw to the host machine's LAN IP**

On each client machine, add its own MCP registration in that machine's `~/.openclaw/openclaw.json`:

```json
{
  "mcpServers": {
    "finmind-tw": {
      "url": "http://192.168.x.x:9123/sse",
      "transport": "sse"
    }
  }
}
```

Replace `192.168.x.x` with the actual IP address of the machine running the Docker container.

**3. Update `docker-compose.yml` port binding**

Make sure the port mapping in `docker-compose.yml` binds to `0.0.0.0` as well:

```yaml
ports:
  - "0.0.0.0:9123:9123"
```

> **Security note**: Binding to `0.0.0.0` exposes the MCP server to your entire LAN. Do not do this if you are on an untrusted network. For personal home use behind a router NAT, this is generally safe.

## OpenClaw MCP Registration

Reference config: [mcp/openclaw-financial-tw.example.json](/home/node/.openclaw/workspace/projects/openclaw-financial-tw/mcp/openclaw-financial-tw.example.json)

The important point is that OpenClaw 2026 expects a network transport for Gateway MCP registration. The maintained path here is SSE.

**Both Mode A and Mode B require the same MCP registration in `openclaw.json`.** The MCP server is always accessed via SSE URL — whether it runs as a local process or inside a container is transparent to OpenClaw.

Add this entry to your `~/.openclaw/openclaw.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "finmind-tw": {
      "url": "http://127.0.0.1:9123/sse",
      "transport": "sse"
    }
  }
}
```

Then validate and reload:

```bash
openclaw config validate
openclaw gateway restart
```

> **Note for Mode B users**: If you plan to connect multiple OpenClaw instances from different machines on the same LAN to a single MCP Docker container, see the [Multi-Client LAN Access](#multi-client--lan-access-mode-b) section below for the required additional configuration.

## Morning Briefing Automation

There are two supported paths:

### Local convenience wrapper

The local wrapper is:

```bash
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/send_tw_morning_briefing.sh
```

It does all of the following:

- uses the project virtualenv
- generates the Taiwan morning briefing
- reads `TW_MORNING_DELIVERIES` from `.env`
- sends to Discord / LINE through `openclaw message send`
- fails fast if no delivery targets are configured

Required `.env` fields for delivery:

```dotenv
TW_MORNING_DELIVERIES=discord:user:YOUR_DISCORD_USER_ID,line:YOUR_LINE_USER_ID
TW_MORNING_ANNOUNCEMENT_LIMIT=8
TW_MORNING_TIMEOUT_SECONDS=180
```

### Recommended scheduled delivery path

For scheduled delivery, prefer OpenClaw cron jobs with provider-specific `delivery` blocks.
In practice this means:

- one 08:30 Discord job
- one 08:30 LINE job

This avoids cross-provider messaging restrictions from a Discord-bound chat context.

## 08:30 Scheduler

The intended schedule is 08:30 Asia/Taipei on trading days.

The payload command should use the project virtualenv directly:

```bash
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python -u /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/tw_morning_briefing.py --announcement-limit 8
```

## Validation Checklist

Run these before calling the deployment complete:

```bash
# Mode A: verify Python packages (tqdm is the most commonly missing one)
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/pip list | grep -E "tqdm|finmind|mcp"

# Mode A: verify FinMind API works
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_finmind.py

# Mode A: verify MCP protocol
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_protocol.py

# Mode A: verify SSE endpoint
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_sse.py

# Morning briefing test
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/send_tw_morning_briefing.sh

# Mode B only: verify container packages (run on NAS host)
docker exec finmind-tw-mcp pip list | grep -E "tqdm|finmind|mcp|uvicorn"
```

**If `tqdm` or other packages are missing in either environment**, install them and rerun the relevant test before continuing.

## Sharing with Friends

The repo intentionally excludes `.venv` and any local `.env`. Your friend follows the steps below depending on their chosen deployment mode.

### Friend runs Mode A (local venv)

```bash
# 1. Clone the repo and cd into it
cd openclaw-financial-tw

# 2. Recreate the virtual environment from requirements.txt
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install tqdm   # safety net: finmind sometimes misses this transitive dep

# 3. Verify all required packages are present
.venv/bin/pip list | grep -E "tqdm|finmind|mcp|uvicorn"
# Expected output: tqdm, finmind, mcp, uvicorn all listed

# 4. Copy and fill .env
cp .env.example .env
# Edit .env: set FINMIND_TOKEN, TW_MORNING_DELIVERIES, etc.

# 5. Start the MCP server
bash scripts/run_finmind_sse.sh

# 6. Validate
.venv/bin/python scripts/verify_mcp_sse.py
```

### Friend runs Mode B (Docker)

```bash
cd openclaw-financial-tw
cp .env.example .env
# Fill FINMIND_TOKEN in .env
docker compose up -d --build
# Docker installs all packages automatically from requirements.txt

# Verify container packages
docker exec finmind-tw-mcp pip list | grep -E "tqdm|finmind|mcp|uvicorn"
```

## Security Notes

- Keep real tokens only in local `.env`. Do not commit them.
- Do not share your `.env` with friends.
- Friends should use their own FinMind and Fugle credentials when possible.
- Delivery targets are personal and should be configured per user in each copied deployment.
