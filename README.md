# openclaw-financial-tw

讓 OpenClaw 成為你的台股研究助理——自動晨報、個人化研究快照、財報分析，全在同一個 AI 介面中完成。

---

## ✨ 功能特色

- **台股晨間簡報**：每日 08:30 自動發送到 Discord / LINE（三大法人、大盤指數、美股夜盤、重大訊息、法說會行程）
- **27+ 個 MCP Tools**：涵蓋技術面（股價/K線）、基本面（財報三表/月營收）、籌碼面（三大法人/融資融券）、總經（CPI/GDP/利率/匯率）
- **並行資料抓取**：晨報 10 個資料源平行抓取，延遲最小化
- **錯誤隔離**：任一資料源失敗不影響整體輸出，失敗來源明確提示
- **跨平台支援**：Mode A（本機直接跑）或 Mode B（Docker 隔離）
- **零成本資料**：FinMind + TWSE + CBC + DGBAS 官方資料，免費（非商業用途）

---

## 🏗 系統架構

```
┌──────────────────────────┐
│    OpenClaw Agent        │
│  skills/tw-* (Markdown)  │
└──────────┬───────────────┘
           │ MCP tool calls
           ▼
┌──────────────────────────┐
│  MCP SSE Server           │
│  finmind_server.py        │
│  Port 9123 (SSE)         │
└──────────┬───────────────┘
           │ API calls
    ┌──────┴──────┐
    │             │
 FinMind API  CBC / DGBAS
 (台股資料)   (總經資料)
```

---

## 🚀 快速開始

### 環境需求

- Python 3.11+
- FINMIND_TOKEN（[免費申請](https://finmindtrade.com/)，一小時 600 次）
- 選配：FUGLE_API_KEY（[申請](https://developer.fugle.tw/)，即時報價備援）

---

### 安裝方式一：Mode A（本機直接跑）

```bash
# 1. 複製專案
git clone https://github.com/cguhenry/openclaw-financial-tw.git
cd openclaw-financial-tw

# 2. 建立虛擬環境（從 requirements.txt 還原）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install tqdm   # safety net

# 3. 填入 API Key
cp .env.example .env
# 用文字編輯器打開 .env，填入 FINMIND_TOKEN

# 4. 啟動 MCP SSE 伺服器
bash scripts/run_finmind_sse.sh

# 5. 註冊到 OpenClaw（編輯 ~/.openclaw/openclaw.json）
# 見「OpenClaw MCP 設定」章節

# 6. 驗證
.venv/bin/python scripts/verify_mcp_sse.py
```

### 安裝方式二：Mode B（Docker）

```bash
git clone https://github.com/cguhenry/openclaw-financial-tw.git
cd openclaw-financial-tw

cp .env.example .env
# 填入 FINMIND_TOKEN

docker compose up -d --build

# 驗證
docker exec finmind-tw-mcp pip list | grep -E "tqdm|finmind|mcp|uvicorn"
```

---

## ⚙️ OpenClaw MCP 設定

在 `~/.openclaw/openclaw.json` 的 `mcpServers` 區塊加入：

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

```bash
openclaw config validate
openclaw gateway restart
```

---

## 📬 晨報自動發送（Discord / LINE）

### 方式一：手動觸發

```bash
# 編輯 .env 中的 TW_MORNING_DELIVERIES
# 例如：TW_MORNING_DELIVERIES=discord:user:你的Discord_ID,line:你的LINE_ID

bash scripts/send_tw_morning_briefing.sh --send
```

### 方式二：每日 08:30 自動發送（OpenClaw cron）

建議建立兩個 cron job（避免跨平台限制）：

| 名稱 | 發送目標 |
|------|---------|
| `tw-morning-briefing-0830-discord` | Discord |
| `tw-morning-briefing-0830-line` | LINE |

排程命令：
```
/path/to/.venv/bin/python -u scripts/tw_morning_briefing.py --announcement-limit 8
```

---

## 📚 文件地圖

| 檔案 | 用途 |
|------|------|
| [docs/DEPLOYMENT-ZH.md](docs/DEPLOYMENT-ZH.md) | **繁體中文**部署與使用說明（完整教學）|
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | **英文版**部署說明 |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 開發歷程、維護手冊、技術決策記錄 |
| [docs/USAGE.md](docs/USAGE.md) | 日常使用指南 |
| [openclaw-financial-tw-plan.md](openclaw-financial-tw-plan.md) | 專案規劃書（包含 Phase 0–6 藍圖）|

---

## 🛠 可用 MCP Tools

| 分類 | Tools |
|------|-------|
| 技術面 | `get_stock_price_daily`, `get_per_pbr`, `get_taiex_index`, `get_taiex_total_return_index` |
| 基本面 | `get_income_statement`, `get_balance_sheet`, `get_cash_flow_statement`, `get_month_revenue`, `get_dividend_policy`, `get_exdividend_result` |
| 籌碼面 | `get_institutional_flows`, `get_margin_short_sale`, `get_shareholding_dist`, `get_foreign_holding_pct`, `get_broker_trading` |
| 總經 | `get_usd_ntd_rate`, `get_interest_rates`, `get_money_supply`, `get_cpi_data`, `get_gdp_data` |
| 整合工具 | `get_tw_market_briefing`, `get_equity_research_snapshot`, `get_major_announcements`, `get_investor_conference_events` |

共 **27 個** MCP tools。

---

## 🤝 貢獻指南

歡迎提交 Issue 或 Pull Request！貢獻時請注意：

- 新增 tool 請同步更新 `mcp/finmind_server.py` 和本文檔的「可用 MCP Tools」章節
- 文件更新請一併修改 `DEPLOYMENT-ZH.md`（繁體中文）和 `DEPLOYMENT.md`（英文）
- 確認 `verify_mcp_*.py` 測試都能通過

---

## ⚠️ 授權與限制

| 項目 | 說明 |
|------|------|
| FinMind | 免費版僅限**教育、非商業用途**，商業使用請至 [finmindtrade.com](https://finmindtrade.com/) 升級 |
| Fugle API | 基本方案免費 |
| TWSE / MoPS / CBC / DGBAS | 政府開放資料，完全免費 |
| Anthropic financial-services | Apache 2.0（本專案 fork 自該專案之概念框架）|
| 本專案 | Apache 2.0 |

**本專案不構成投資建議。所有資料僅供參考。**

---

## 📝 維護日誌

- **2026-05-21** — Bug 修復（`_load_dotenv` 重讀、market briefing error isolation、GDP 動態 end_time、equity snapshot 並行化、exdividend/taiex_index 新增、晨報 renderer 過期法說過濾）
- **2026-05-20** — Port 8000→9123、DEPLOYMENT.md、DEPLOYMENT-ZH.md、USAGE.md、Docker Compose 完成
- **2026-05-19** — Phase 0–5 完成，27 MCP tools，上線晨報排程