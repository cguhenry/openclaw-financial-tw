# OpenClaw Financial TW Usage

## Core Usage Model

Use this project through OpenClaw skills plus the `finmind-tw` MCP server.

Main visible skills:

- `tw-morning-briefing`
- `tw-market-researcher`
- `tw-equity-research`
- `tw-earnings-calendar`
- `tw-sector-overview`
- `tw-dcf-model`
- `tw-comps`
- `tw-financial-statements`

## Common Workflows

### 1. Generate a Taiwan Morning Brief

Manual local run:

```bash
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/tw_morning_briefing.py
```

Manual send using `.env` targets:

```bash
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/send_tw_morning_briefing.sh
```

### 2. Research a Single Stock

Use the `tw-equity-research` or `tw-market-researcher` skill and start from:

- `get_equity_research_snapshot(stock_id, start_date)`

The snapshot bundles:

- price
- PER/PBR
- monthly revenue
- income statement
- institutional flows
- major announcements

### 3. Produce a Market-Wide Brief

Start from:

- `get_tw_market_briefing(announcement_limit=...)`

It bundles:

- USD/NTD
- CBC policy rate
- M2
- CPI
- GDP
- US market read-through
- TWSE institutional summary
- TAIEX total-return context
- major announcements
- investor conference events

## Delivery Target Format

Morning briefing delivery targets use:

```text
channel:target
```

Examples:

- `discord:user:768728802070626334`
- `line:U6471476a34c92577e2ac7814f27b8b28`

Multiple targets go in one env var, comma-separated:

```dotenv
TW_MORNING_DELIVERIES=discord:user:ME,line:MY_LINE_ID,discord:user:FRIEND_A
```

For exact scheduled delivery, prefer one cron job per provider instead of relying on a Discord-bound session to push directly into LINE.

## Sharing With A Few Friends

The safe sharing model is:

1. Share the repository code, not your live `.env`
2. Let each friend create their own `.env` from `.env.example`
3. Let each friend fill their own:
   - `FINMIND_TOKEN`
   - optional `FUGLE_API_KEY`
   - `TW_MORNING_DELIVERIES`
4. Let each friend point delivery only to their own Discord / LINE target
5. Let each friend create their own 08:30 cron jobs for Discord and/or LINE

This avoids exposing:

- your API keys
- your Discord user target
- your LINE target

## Minimal Friend Onboarding

Ask each friend to do only this:

```bash
cd /path/to/openclaw-financial-tw
cp .env.example .env
# fill their own token and targets
docker compose up -d --build
```

Then verify:

```bash
bash scripts/send_tw_morning_briefing.sh
```

## Current Limits

- The logical Taiwan research roles are described in `tw-market-researcher`, but they currently run through one combined MCP server, not three separately deployed MCP services.
- This system is a research assistant and automation layer, not a brokerage or execution system.
- The project includes a non-investment-advice disclaimer in generated briefing output; keep that intact when sharing.
