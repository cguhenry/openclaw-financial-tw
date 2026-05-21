# Phase 1 / 1.5 / 2 Status - OpenClaw Taiwan Financial Services

Date: 2026-05-19

## Phase 1 - Local MCP Server

Status: completed

- `mcp/finmind_server.py` now exposes 14 read-only tools.
- Direct verification passed with:
  - daily price
  - income statement
  - monthly revenue
  - institutional flows
  - dividend policy
  - realtime quote
- MCP stdio protocol verification passed with tool listing and sample calls.

## Phase 1.5 - OpenClaw HTTP/SSE Wiring

Status: completed

- Confirmed the local `openclaw.json` schema accepts HTTP MCP transports (`sse`, `streamable-http`) but rejects `stdio`.
- Restored `~/.openclaw/openclaw.json` `finmind-tw` entry to:
  - `url: http://127.0.0.1:9123/sse`
  - `transport: sse`
- Updated `mcp/finmind_server.py` so the same server can run in either:
  - `sse` mode by default for OpenClaw runtime registration
  - `stdio` mode when explicitly requested for local protocol tests
  - `streamable-http` mode when explicitly requested for future Gateway compatibility
- Added `scripts/run_finmind_sse.sh` launcher.
- Added `scripts/verify_mcp_sse.py` reachability check.
- Validation passed:
  - `openclaw config validate`
  - HTTP `200` from `/sse`
  - `content-type: text/event-stream`

## Phase 2 - Functional Expansion

Status: completed and validated

- Added `get_realtime_quote(stock_id)` backed by Fugle intraday quote API.
- Expanded `get_major_announcements(...)` to use the official MOPS realtime major-announcements table by default:
  - `market`: `all`, `sii`/TWSE/listed, `otc`/TPEx, `rotc`/emerging, `pub`
  - richer normalized fields: company name, market label, ROC/ISO dates, local time, sequence number, category, and official detail URL
  - `summary_count`: compact recent-N headline summary
  - `include_details`: optional official detail-page enrichment with speaker, clause, fact date, and description
- Kept the TWSE homepage instant feed `https://www.twse.com.tw/res/data/zh/home/news.json` as fallback.
- Added `get_foreign_holding_pct(stock_id, start_date, end_date?)` for Phase 3 chip-analysis workflows.
- Expanded validation scripts so Phase 2 coverage is part of the normal smoke tests.
- Current verified MCP tool count: 14.

## Major Announcements Source Note

- Implemented `get_major_announcements(stock_id=None, market="all", limit=20, summary_count=5, include_details=False)` using the official MOPS page `https://mopsov.twse.com.tw/mops/web/t05sr01_1` and Ajax endpoint `https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1`.
- Market `TYPEK` mapping verified:
  - `all`: 全體公司
  - `sii`: 上市公司
  - `otc`: 上櫃公司
  - `rotc`: 興櫃公司
  - `pub`: 公開發行公司

## Phase 3 - Taiwan Skill Layer

Status: completed initial implementation and validated

- Added OpenClaw-visible skills:
  - `tw-dcf-model`
  - `tw-comps`
  - `tw-chip-analysis`
  - `tw-earnings-analysis`
  - `tw-financial-statements`
- Validation passed:
  - `openclaw skills check`
  - new skills are visible to model and available as commands

## Phase 4 - Macro Data and Sector Analysis

Status: completed initial implementation and validated

- Added official Taiwan macro data tools to the existing `finmind-tw` MCP server:
  - `get_usd_ntd_rate(frequency="daily"|"monthly"|"yearly", start_date?, end_date?, max_rows?)`
  - `get_interest_rates(max_rows?)`
  - `get_money_supply(measure="M1A"|"M1B"|"M2", basis="average"|"end_of_period", max_rows?)`
  - `get_cpi_data(max_rows?)`
  - `get_gdp_data(start_time?, end_time?, max_rows?)`
  - `get_taiex_total_return_index(start_date, end_date?, max_rows?)`
- Official sources used:
  - CBC USD/NTD closing rate CSVs
  - CBC policy-rate CSV
  - CBC money-supply CSVs
  - DGBAS CPI XML and GDP SDMX-JSON
  - FinMind TAIEX total-return index
- Added OpenClaw-visible skill:
  - `tw-sector-overview`
- Validation passed:
  - `verify_mcp_finmind.py`
  - macro tool direct spot checks
  - MCP stdio protocol test with tool listing and sample macro calls
  - live SSE endpoint check
  - `openclaw config validate`
  - `openclaw skills check`
- Current verified MCP tool count: 23 after adding DGBAS GDP.
- HTTP helper now retries transient official-site connection resets before failing the tool call.

## Phase 5 - Advanced Agent Integration

Status: completed initial implementation and validated

- Added MCP integration tools:
  - `get_tw_market_briefing(announcement_limit?)`
  - `get_investor_conference_events(limit?)`
  - `get_equity_research_snapshot(stock_id, start_date?)`
- Added OpenClaw-visible skills:
  - `tw-equity-research`
  - `tw-morning-briefing`
  - `tw-earnings-calendar`
- Validation passed:
  - direct Phase 5 spot checks for events, briefing, and equity snapshot
  - MCP stdio protocol test: `tools=22 required=ok`
  - live SSE endpoint check
  - `openclaw config validate`
  - `openclaw skills check`
- Note: GDP data is not implemented yet because a stable official machine-readable DGBAS endpoint was not confirmed during this pass.
