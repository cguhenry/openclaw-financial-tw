# Phase 0 Report - OpenClaw Taiwan Financial Services

Date: 2026-05-19

## Feasibility

Feasible. Anthropic's `financial-services` repository is a Claude Plugin bundle whose core financial-analysis skills are Markdown-based and can be installed into OpenClaw's skill directory with minimal format changes. The bundled MCP connectors are mostly premium HTTP connectors and do not materially solve Taiwan-market coverage, so Taiwan data should be implemented as local MCP servers.

## Upstream Snapshot

- Repository: `https://github.com/anthropics/financial-services`
- Local path: `projects/anthropic-financial-services`
- Snapshot checked: `9affc6e`
- Core plugin reviewed: `plugins/vertical-plugins/financial-analysis`

## Phase 0 Actions

- Cloned upstream financial-services repository locally.
- Reviewed `financial-analysis` command and skill structure.
- Installed upstream financial-services skills into `skills/`.
  - 54 of 55 upstream skills are installed.
  - The only skipped upstream skill is Claude's bundled `skill-creator`, because this workspace already has an OpenClaw/Codex-specific `skill-creator`.
  - Inventory: `projects/openclaw-financial-tw/upstream/skill-inventory.md`.
- Preserved upstream slash-command source files under `projects/openclaw-financial-tw/upstream/commands/` for later OpenClaw command binding.
- Prepared a Taiwan-specific OpenClaw skill scaffold: `skills/tw-financial-analysis`.
- Prepared a local project workspace: `projects/openclaw-financial-tw`.
- Stored API credentials in a local ignored env file, not in committed docs.
- Added a deterministic source verification script for FinMind, TWSE, and Fugle.
- Created a project Python virtual environment at `projects/openclaw-financial-tw/.venv`.
- Installed MCP and data SDK dependencies in the project venv, not system Python.
- Added a minimal stdio MCP server at `projects/openclaw-financial-tw/mcp/finmind_server.py`.

## Compatibility Notes

- OpenClaw skill compatibility: high for `SKILL.md` folders.
- Claude Plugin slash commands need adaptation before they become OpenClaw-native commands.
- Anthropic Managed Agents YAML files are useful references, but not directly runnable as OpenClaw managed agents without a bridge.
- External paid MCP connectors should remain optional. Taiwan coverage should prioritize FinMind, TWSE/TPEx, MoPS, CBC, and DGBAS.

## Data Source Validation

Run:

```bash
cd /home/node/.openclaw/workspace/projects/openclaw-financial-tw
set -a
. ./.env
set +a
python3 scripts/verify_phase0_sources.py
```

Expected checks:

- FinMind: `TaiwanStockPrice` for `2330`
- TWSE OpenAPI: `STOCK_DAY_ALL`
- Fugle: intraday quote endpoint for `2330`

Latest result: all three checks passed on 2026-05-19 using the stored private env file.

## MCP FinMind Status

Implemented first-pass read-only tools:

- `get_stock_price_daily`
- `get_income_statement`
- `get_balance_sheet`
- `get_cash_flow_statement`
- `get_month_revenue`
- `get_institutional_flows`
- `get_margin_short_sale`
- `get_dividend_policy`
- `get_per_pbr`
- `get_shareholding_dist`
- `get_broker_trading`

Validation:

- `scripts/verify_mcp_finmind.py`: direct function smoke test passed for price, income statement, monthly revenue, institutional flows, and dividend policy.
- `scripts/verify_mcp_protocol.py`: stdio MCP protocol smoke test passed; 11 tools listed and a sample `get_stock_price_daily` call succeeded.
- `openclaw skills check`: passed; `tw-financial-analysis` and the imported upstream finance skills are visible to the model.

Config note:

- OpenClaw schema supports stdio MCP entries with `command`, `args`, `cwd`, and `transport`.
- A direct `config.patch` attempt for `mcp.servers.finmind-tw` was refused because those paths are protected by the gateway config editor.
- The working server config remains in `mcp/openclaw-financial-tw.example.json`; registration should be done through the supported OpenClaw configuration path or a controlled full config apply.

## Environment Notes

Python is available as `/usr/bin/python3` 3.11.2. Henry has restored `ensurepip`, so project-local venv installs work. System-level `pip install --break-system-packages` is acceptable if needed later, but not currently required.

## Recommended Next Step

Start Phase 1 with `mcp-finmind` as the first local MCP server. Implement read-only tools first:

- `get_stock_price_daily`
- `get_income_statement`
- `get_balance_sheet`
- `get_cash_flow_statement`
- `get_month_revenue`
- `get_institutional_flows`
- `get_margin_short_sale`
- `get_dividend_policy`

Keep Fugle as an optional quote fallback until its API shape is confirmed against the current token.
