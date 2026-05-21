# Phase 4 Macro and Sector Status

Date: 2026-05-19

## Implemented MCP Tools

- `get_usd_ntd_rate`
  - Source: CBC
  - Daily CSV: `https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData015.csv`
  - Monthly CSV: `https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData016.csv`
  - Yearly CSV: `https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData017.csv`
- `get_interest_rates`
  - Source: CBC
  - CSV: `https://www.cbc.gov.tw/public/data/OpenData/經研處/EG28D01.csv`
- `get_money_supply`
  - Source: CBC
  - Daily-average monthly CSV: `https://www.cbc.gov.tw/public/data/OpenData/經研處/EF15M01.csv`
  - Month-end monthly CSV: `https://www.cbc.gov.tw/public/data/OpenData/經研處/EF17M01.csv`
- `get_cpi_data`
  - Source: DGBAS
  - XML: `https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/230556/pr0104a1m.xml`
- `get_gdp_data`
  - Source: DGBAS
  - SDMX-JSON endpoint pattern: `https://nstatdb.dgbas.gov.tw/dgbasAll/webMain.aspx?sdmx/A018101010/1+2+3+4+5+6+7+8+9+10+11+12+13+14+15...Q.&startTime=<year>&endTime=<year-Qn>`
  - Dataflow: `A018101010` 國民所得統計常用資料
- `get_taiex_total_return_index`
  - Source: FinMind
  - Dataset: `TaiwanStockTotalReturnIndex`, `data_id=TAIEX`

## Implemented Skill

- `skills/tw-sector-overview/SKILL.md`

## Verification

- Direct smoke test: passed, including CBC, DGBAS, FinMind, Fugle, and MOPS calls.
- MCP stdio protocol test: passed, `tools=19 required=ok`.
- SSE endpoint: passed, HTTP 200 with `text/event-stream`.
- `openclaw config validate`: passed.
- `openclaw skills check`: `tw-sector-overview` visible and available.
- Transient official-site connection resets are retried in the shared text-fetch helper.

## Deferred

- DGBAS SDMX base endpoints provided by Henry were checked and resolved:
  - `https://nstatdb.dgbas.gov.tw/dgbasall/webMain.aspxSDMX`
  - `https://nstatdb.dgbas.gov.tw/dgbasall/webMain.aspx?sdmx/`
- Result: the service exists, but bare base calls return request rejection or `功能代號不存在`; Henry supplied the working SDMX dataflow/key path for GDP, and `get_gdp_data` is now implemented and verified.
- SEMI Book-to-Bill is not implemented as structured data because no stable official machine-readable source was confirmed. Use source-search workflow in `tw-sector-overview` for SEMI/SEMI.org, Digitimes, TechNews, MoneyDJ, and Anue reports when the indicator is needed.
