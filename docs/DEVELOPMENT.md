# OpenClaw Financial TW 開發歷程與維護手冊

> 本文件記錄 `openclaw-financial-tw` 專案的完整開發過程、技術決策、後續維護方向，以及交接給新開發者所需的一切上下文。
> 
> **預設讀者**：接手維護或繼續開發本專案的工程師。
> **最後更新**：2026-05-20

---

## 一、專案起源與目標

### 1.1 為何會有這個專案

`anthropics/financial-services` 是一個以西方（特別是美股）為中心的開源金融分析技能庫。Henry 的需求很直接：OpenClaw 已經是他的個人 AI 助理，他也習慣在上面做研究，但這個技能庫對台灣股市幾乎是空白——沒有 TAIEX、沒有三大法人資料、沒有繁體中文財報解析、沒有任何台灣總經數據。

這個專案的目的，就是把 OpenClaw 變成一個合格的「台股研究助理」。

### 1.2 核心目標

1. **讓 OpenClaw 能夠查詢台灣股市資料**：股價、財報、籌碼、重大訊息、總經數據
2. **建立台灣版的財務分析技能**：DCF、Comps、Chip Analysis、晨報自動推送
3. **以最少成本達成**：所有資料來源原則上免費（非商業用途），不需要訂閱 TEJ 或 CMoney

### 1.3 授權與使用限制

| 項目 | 說明 |
|------|------|
| FinMind | 免費版僅限**教育、非商業用途**。商業產品上線前需升級付費方案。|
| Fugle API | 基本方案免費，用於歷史日K 與即時報價備援。|
| TWSE / MoPS / CBC / DGBAS | 政府開放資料，完全免費。|
| Anthropic financial-services | Apache 2.0，可自由 fork 與修改。|

**本專案不構成投資建議。** 所有輸出資料僅供參考。

---

## 二、計畫與實作對照

原始計畫（`openclaw-financial-tw-plan.md`）極為龐大，估計 380 小時（~10–13 週全職）。實際開發採用**精實迭代**，跳過了部分項目，優先交付核心價值。

### 2.1 各 Phase 實作對照表

| Phase | 計畫內容 | 實際完成度 | 說明 |
|-------|---------|----------|------|
| Phase 0 | 環境建置、申請 API Key | ✅ 完成 | FinMind + Fugle 申請完成 |
| Phase 1 | `mcp-finmind` 核心 MCP 伺服器 | ✅ 完成 | 14 個 tool，經 spot check 驗證 |
| Phase 1.5 | OpenClaw SSE 傳輸 wiring | ✅ 完成 | HTTP/SSE，port 9123 |
| Phase 2 | 實時報價、重大訊息、XBRL | ✅ 完成 | Fugle 即時報價 + MOPS 重大訊息 + 外資持股，tool 數從 14 增至 22 |
| Phase 3 | 台灣技能層（DCF / Comps / Chip...）| ✅ 完成 | Skills: tw-dcf-model, tw-comps, tw-chip-analysis, tw-earnings-analysis, tw-financial-statements |
| Phase 4 | 總經資料（GDP / CPI / M2）| ✅ 完成 | Sources: CBC + DGBAS，tool 數增至 23 |
| Phase 5 | Agent 整合與晨報自動化 | ⚠️ 部分完成 | Skills 完成；晨報 cron 最初斷過，2026-05-20 修復並建立兩路發送（Discord + LINE）|
| Phase 6 | 測試、部署、合規、文件 | ⚠️ 部分完成 | Docker + compose 完成；DEPLOYMENT.md / USAGE.md 後補；`.env.example` 完成；未做單元測試套件 |

### 2.2 跳過或延後的項目

| 項目 | 原因 |
|------|------|
| TEJ / TCRI 法人預估 EPS | 付費項目，且需要商業授權；多數散戶/個人研究者不需要 |
| SEMI Book-to-Bill 結構化資料 | 沒有穩定的機器可讀資料源，改為在 `tw-sector-overview` skill 中以 search workflow 替代 |
| XBRL 附表解析（關聯人交易等）| 已有 FinMind 主體財報；XBRL 解析依賴 `arelle`，增加部署複雜度 |
| 單元測試覆蓋率報告 | 時程考量；目前以 spot check 驗證替代 |
| ClawHub 開源發布 | 仍為個人使用，未到社群發布階段 |

---

## 三、系統架構

### 3.1 整體架構圖

```
┌──────────────────────────────────────────────┐
│         OpenClaw Agent (AI 大腦)              │
│  技能層：skills/tw-* (Markdown SKILL.md)      │
└──────────────────┬───────────────────────────┘
                    │ MCP tool calls
                    ▼
┌──────────────────────────────────────────────┐
│    MCP SSE Server (finmind_server.py)         │
│  Port: 9123                                   │
│  模式: SSE (預設) / stdio (測試) / streamable-http │
│  23+ tools，含技術面/基本面/籌碼面/總經        │
└──────────────────┬───────────────────────────┘
                    │ API calls
         ┌──────────┴──────────┐
         ▼                     ▼
   FinMind API            CBC / DGBAS
   (主力資料源)           (總經資料)
```

### 3.2 技能層（Skills）

| 技能 | 指令 | 功能 |
|------|------|------|
| `tw-morning-briefing` | — | 晨間簡報生成（排程自動發送）|
| `tw-market-researcher` | — | 台股研究統整 skill，協調多資料源 |
| `tw-equity-research` | — | 個股研究報告生成 |
| `tw-earnings-calendar` | — | 法說會與財報時程追蹤 |
| `tw-dcf-model` | `/twdcf` | 台灣版 DCF 估值 |
| `tw-comps` | `/twcomps` | 同業比較分析 |
| `tw-chip-analysis` | `/twchip` | 籌碼面分析 |
| `tw-earnings-analysis` | `/twearnings` | 財報季分析 |
| `tw-financial-statements` | `/twfs` | 繁中財報解析 |
| `tw-sector-overview` | `/twsector` | 產業分析 |

### 3.3 MCP 工具（MCP Server）

所有工具集中在 `mcp/finmind_server.py`，共 23+ 個 tool，分為四類：

**技術面**
- `get_stock_price_daily` / `get_stock_price_realtime`
- `get_per_pbr`
- `get_taiex_index` / `get_taiex_total_return_index`

**基本面**
- `get_income_statement` / `get_balance_sheet` / `get_cash_flow_statement`
- `get_month_revenue`
- `get_dividend_policy` / `get_exdividend_result`

**籌碼面**
- `get_institutional_flows`
- `get_margin_short_sale`
- `get_shareholding_dist` / `get_foreign_holding_pct`
- `get_broker_trading`

**總經**
- `get_usd_ntd_rate`
- `get_interest_rates`
- `get_money_supply`
- `get_cpi_data`
- `get_gdp_data`

**整合工具（Phase 5）**
- `get_tw_market_briefing` — 晨報（全框一次抓完）
- `get_investor_conference_events` — 法說會行程
- `get_equity_research_snapshot` — 個股研究快照

### 3.4 資料來源優先順序

```
行情 / 財報：FinMind → TWSE OpenAPI（fallback）
即時報價：Fugle → TWSE（收盤後）
籌碼面：FinMind → TWSE
重大訊息：MOPS 官網 Ajax → TWSE 首頁（fallback）
總經：CBC / DGBAS 官方 CSV
```

---

## 四、技術決策記錄

### 4.1 為何選擇 SSE 而非 stdio 作為主要傳輸？

**問題**：OpenClaw 2026+ 版本的 MCP 設定需要網路傳輸格式，不接受 `stdio`。

**選擇**：SSE（Server-Sent Events）。

**替代方案考慮過**：
- `streamable-http`：OpenClaw 有支援但需要額外設定 header，文件不足，先跳過
- 直接 stdio：被 OpenClaw 2026 的新設定擋住

**結論**：`finmind_server.py` 現在支援三種模式啟動：
```python
# SSE（預設，供 OpenClaw 讀取）
python finmind_server.py

# stdio（本地測試）
python finmind_server.py --transport stdio

# streamable-http（未來探索）
python finmind_server.py --transport streamable-http
```

### 4.2 為何 port 從 8000 改為 9123？

Henry 的 NAS 另一個服務已占用 8000。改 port 準則：
- 只改 `.env`/`.env.example`/`docker-compose.yml`/`Dockerfile` 這四個設定源
- Python 程式碼透過 `MCP_PORT` 環境變數讀取，不硬寫
- 所有文件同步更新

### 4.3 為何晨報 cron 是兩個獨立的 job？

Discord 和 LINE 是不同平台。從 Discord 綁定的 OpenClaw 會話嘗試直接發 LINE，會被跨平台限制擋住。解決方式：兩個獨立的 cron job，各自綁定自己的 `delivery` channel，各自抵達各自的平台。

### 4.4 為何 FinMind 是主力而非 TWSE OpenAPI？

FinMind 提供的欄位更完整（包含還原股價、分點、融資券等），且 Python SDK 使用簡單。TWSE OpenAPI 主要作為 fallback。

### 4.5 為何不用 `arelle` 做 XBRL 解析？

`arelle` 是完整的 XBRL 工具鏈，但包裝繁瑣。FinMind 已經把 XBRL 轉好成 pandas DataFrame，而且主要分析工作流需要的「財報三表」已有完整覆蓋。純 XBRL 解析延後處理。

---

## 五、開發歷程（逐 phase 記錄）

### 2026-06-06：股票分析儀表板（Dashboard）增量開發記錄

本段記錄建立在既有 `openclaw-financial-tw` repo 內的 dashboard 子系統，採「不另開 repo、在原專案內擴充」策略。

#### 決策摘要

- **不另開新專案**：儀表板直接放在 `dashboard/api` 與 `dashboard/web`，避免資料層重複維護。
- **部署改為 Docker-first**：優先支援 NAS、一般 Docker Host、本機開發與輕量 VPS；Synology 僅做部署文件差異化，不把路徑硬寫進通用 compose。
- **報價模式雙軌**：前端必須同時支援 `即時自動報價` 與 `使用者手動更新`。
- **前端 API 走同 origin**：瀏覽器不直接打 `:9180`，改為由 web 容器代理 `/api` 到 dashboard API，解決同區網 NAS 存取時的 `Failed to fetch` / CORS 問題。

#### Phase 0：部署與工程骨架

**主要產出**

- `docker-compose.yml` 納入 dashboard profile
- `.env.example` 補齊 dashboard 相關變數（quote/chart/analysis TTL、CORS、port）
- `docs/deploy-nas.md` 新增 Synology NAS 啟動、驗證、CORS 與常見錯誤排查
- README 補上 dashboard 啟動與同 origin API proxy 說明

**關鍵做法**

- web 容器用 Nginx 代理 `/api/*` → `stock-dashboard-api:9180`
- Vite dev server 也配置 `/api` proxy，讓本機開發與 Docker 行為一致
- 外部對外 port 預設改為 `9080`，避開 NAS 上既有 `8080` 衝突

#### Phase 1：MVP 畫面與 API/BFF

**主要產出**

- 新增 `dashboard/api` FastAPI 服務
- 新增 `/api/health`、`/api/stocks/{stock_id}/quote`、`/api/stocks/{stock_id}/chart`、`/api/stocks/{stock_id}/refresh`
- 新增 `dashboard/web` React + Vite 單頁前端
- 完成深色儀表板骨架、股票代號輸入、報價模式切換、股票標頭、日線 K 棒與成交量

**資料策略**

- quote / chart 由 dashboard API 包住既有 `mcp/finmind_server.py`，避免前端直接碰原始資料源
- 加入簡單 TTL cache，降低同一股票反覆查詢時的延遲與 API 壓力

#### Phase 5.5：提醒預覽延遲優化與收尾

**問題**

- `AlertCenter` 首次載入時，原本會額外呼叫一次 `/ai-alert-preview`
- 若 `signals` 尚未有快取，這條路徑會再觸發一次分析/預測鏈，導致提醒中心首次開啟偏慢

**修正**

- 前端 `AlertCenter` 改成優先重用主頁已取得的 `analysis` 與 `signals`
- 後端 `AlertService.build_ai_preview()` 新增獨立 TTL cache：`ai-alert-preview:{stock_id}`
- 保留 `/api/stocks/{stock_id}/ai-alert-preview`，但降為 fallback 路徑，而非首屏必要依賴

**效果**

- 使用者首次打開 dashboard 時，AI 建議價位可直接從現有 payload 組裝，不必再等第二條重路徑
- API 仍保留可獨立呼叫的 preview 端點，方便之後拆頁、背景預抓或第三方整合

#### Phase 2：技術分析第一輪落地

**主要產出**

- 新增 `/api/stocks/{stock_id}/analysis`
- 後端完成：
  - MA5 / MA20 / MA60
  - Bollinger Bands
  - KD
  - MACD
  - 關鍵價位（壓力 / 回檔 / 支撐）
  - 技術總覽與指標總表
- 前端完成：
  - 主圖疊加布林通道
  - 同面板子圖：成交量、KD、MACD
  - 主圖關鍵價位標線
  - 右側技術分析總覽面板
  - 獨立技術指標表格元件

**文案規則**

- 技術總覽不再只回傳簡單的「多頭 / 空頭 / 中性」
- 綜合判讀會同時考慮：
  - 均線排列
  - 布林位置與開口
  - 量價關係
  - KD 狀態
  - MACD 狀態
- 目標是讓維護者之後能直接擴充規則，而不是推倒重寫整個 API 結構

#### 驗證方式

- 後端測試：`.venv/bin/python -m pytest -q tests/test_dashboard_api.py`
- 前端建置：`cd dashboard/web && npm run build`
- 介面驗證重點：
  - 同 origin `/api` 是否正常代理
  - 從 NAS IP 存取 `http://<NAS_IP>:9080` 是否仍可載入資料
  - 自動報價模式只更新 quote；手動更新會重抓 quote / chart / analysis

#### 後續維護注意事項

- 若圖表 pane 再變多，優先維持單一資料契約，避免不同元件各自重算不同版本的指標。
- 若未來要做 60 分 K / 週 K，小心不要把日線邏輯硬套到分鐘資料；先明確分離 timeframe 與資料來源。
- 若同區網仍出現 `Failed to fetch`，先檢查 web 容器是否仍有 `/api` reverse proxy，而不是先懷疑 CORS。

#### Phase 3：法人 / 主力 / 多週期面板

**主要產出**

- 新增 `/api/stocks/{stock_id}/institutional`
- 新增 `/api/stocks/{stock_id}/main-force`
- 新增 `/api/stocks/{stock_id}/multi-period`
- 前端新增三大法人表、主力進出燈號卡、多週期縮圖卡

**這一階段最重要的技術決策**

- **主力進出先採 proxy，不假裝是真分點模型。**
  - 原因：FinMind 的 `TaiwanStockTradingDailyReport` 在目前環境回 `HTTP 400`，不足以當穩定 Phase 3 依賴。
  - 目前做法：用「外資 + 投信 + 0.5 倍自營商」組成 `proxy_net`，再搭配外資持股比變化，輸出主力燈號。
  - UI 與 API 都明確標示 `institutional_proxy` 與說明文字，避免誤導後續維護者。

- **多週期縮圖先不硬做 60 分 K。**
  - 短週期視角目前用「近 20 根日 K」替代。
  - 中期用近 60 根日 K。
  - 週 K 由日線重採樣得到。
  - 後續若接入穩定分鐘資料源，再把短週期卡替換成真正 60 分 K，不需要改前端骨架。

**驗證方式**

- `pytest -q tests/test_dashboard_api.py`
- `cd dashboard/web && npm run build`
- 實際檢查：
  - 三大法人表是否有 10 日資料
  - 主力卡是否顯示 method / signal / note
  - 多週期縮圖是否回傳 3 組 period payload

#### Phase 4：型態分析 / 操作建議 / AI 骨架

**主要產出**

- 新增 `/api/stocks/{stock_id}/patterns`
- 新增 `/api/stocks/{stock_id}/signals`
- 前端新增：
  - 型態分析面板
  - 操作建議文字面板
  - 勝率儀表盤
  - 明日方向預測面板

**核心設計原則**

- **型態分析是真的規則，不是 placeholder。**
  - 目前用近 60 根日 K 的局部極值找 W 底 / M 頭輪廓，再檢查對稱性與頸線是否突破/跌破。

- **操作建議是真規則引擎，不是靜態文案。**
  - 會綜合：
    - 趨勢方向
    - 布林位置
    - 關鍵價位
    - W 底 / M 頭型態

- **勝率與方向預測目前是 rule-based skeleton，不是假裝訓練好的 AI。**
  - API 契約已先固定成：
    - `win_rate`
    - `direction_prediction`
    - `basis`
    - `note`
  - 現階段的分數由技術指標、主力 proxy 與型態規則合成。
  - 後續若接入真正模型，只要替換後端計算邏輯即可，不需要改 UI 結構。

**驗證方式**

- `pytest -q tests/test_dashboard_api.py`
- `cd dashboard/web && npm run build`
- API 檢查：
  - `/patterns` 是否回傳 `w_bottom` / `m_top`
  - `/signals` 是否回傳 `trading_suggestion` / `win_rate` / `direction_prediction`

#### Phase 4.5 / 5：60 分 K / 真分點路徑 / 可重訓模型

**主要產出**

- 多週期縮圖的短週期卡，已從「近 20 根日 K 替代視角」改成 **Fugle 真 60 分鐘 K**
- 主力進出 API 新增 **premium 分點路徑**
- 預測 API 從 rule-based skeleton 升級為 **可離線重訓的隨機森林模型**
- 新增後端重訓入口：`POST /api/stocks/{stock_id}/train-models`
- 新增腳本：`scripts/train_dashboard_models.py`

**重要決策**

- **60 分 K 採用 Fugle intraday candles**
  - 實測可用 endpoint：`/stock/intraday/candles/{symbol}?timeframe=60`
  - 因此多週期卡現在是真分鐘資料，不再是假日線替代品。

- **真分點模型採「能用就啟用，不能用就明確 fallback」**
  - FinMind 文件確認 `TaiwanStockTradingDailyReport` 為 sponsor 等級資料，而且請求模式是 `date=單日`。
  - 免費等級會直接回 400 與升級提示，這不是程式 bug。
  - 目前主力面板會：
    - 若 premium 分點資料可用：走 `broker_top20` 真分點模型
    - 若不可用：退回 `institutional_proxy`，並在 UI/說明明確標示

- **預測模型升級為實際可訓練模型**
  - 使用近 4 年日線、技術指標與法人流向特徵
  - 分成：
    - 5 日勝率二元分類
    - 次一交易日方向三元分類
  - 模型檔預設寫到 `dashboard/api/models/`
  - 該目錄已加入 `.gitignore`，避免把機器產出的模型 commit 進 repo

**維護方式**

- 手動離線重訓：
  - `.venv/bin/python scripts/train_dashboard_models.py 2330`
- 或從 API 觸發：
  - `POST /api/stocks/2330/train-models`
- 前端也提供「重訓模型」按鈕，方便 NAS 使用者直接操作

**驗證方式**

- `pytest -q tests/test_dashboard_api.py`
- `cd dashboard/web && npm run build`
- 額外應驗：
  - `/signals` 的 `basis` 是否在有模型時變成 `trained_random_forest`
  - 主力面板的 `method` 是否正確反映 `broker_top20` 或 `institutional_proxy`

### Phase 0：環境建置
**日期**：2026-05-19  
**主要產出**：
- FinMind 帳號申請完成，取得 Token
- Fugle 免費 API Key 取得
- OpenClaw 環境確認
- 完成 `openclaw-financial-tw-plan.md`

---

### Phase 1：MCP 核心（技術面 + 基本面）
**日期**：2026-05-19  
**主要產出**：
- `mcp/finmind_server.py` 初版，14 個 tool
- 驗證：daily price、income statement、monthly revenue、institutional flows、dividend policy
- MCP stdio 協定測試通過

---

### Phase 1.5：OpenClaw SSE 整合
**日期**：2026-05-19  
**主要產出**：
- `scripts/run_finmind_sse.sh` 啟動腳本
- `scripts/verify_mcp_sse.py` 健康檢查
- `~/.openclaw/openclaw.json` 中的 `finmind-tw` 設定（port 9123，SSE transport）
- `openclaw config validate` 通過

---

### Phase 2：實時報價 + 重大訊息（擴充至 22 tools）
**日期**：2026-05-19  
**主要產出**：
- 新增 `get_realtime_quote`：Fugle 即時報價 API
- 新增 `get_major_announcements`：MOPS 官網 Ajax 介接，支援 market 參數過濾
- 新增 `get_foreign_holding_pct`：外資持股比率
- 確認 MOPS market `TYPEK` mapping：`all / sii / otc / rotc / pub`

---

### Phase 3：台灣技能層
**日期**：2026-05-19  
**主要產出**：
- `skills/tw-dcf-model/SKILL.md`（台灣 DCF，含 WACC 台灣化參數）
- `skills/tw-comps/SKILL.md`（同業比較）
- `skills/tw-chip-analysis/SKILL.md`（籌碼分析）
- `skills/tw-earnings-analysis/SKILL.md`（財報季分析）
- `skills/tw-financial-statements/SKILL.md`（繁中財報解析）
- `openclaw skills check` 全部通過

---

### Phase 4：總經資料（tool 數增至 23）
**日期**：2026-05-19  
**主要產出**：
- `get_usd_ntd_rate`：CBC 每日/每月/每年匯率 CSV
- `get_interest_rates`：CBC 利率 CSV
- `get_money_supply`：CBC M1A/M1B/M2 月均/月底
- `get_cpi_data`：DGBAS CPI XML
- `get_gdp_data`：DGBAS SDMX-JSON（用 Henry 提供的正確 endpoint pattern）
- `get_taiex_total_return_index`：FinMind TAIEX 全益指數
- `skills/tw-sector-overview/SKILL.md`

---

### Phase 5：Agent 整合 + 晨報自動化

## 六、2026-06-06：股票分析儀表板（修正版計劃）Phase 0 / Phase 1 與 Phase 2 起手式

**日期**：2026-06-06  
**背景**：Henry 提出要在 `openclaw-financial-tw` 的基礎上，做一個接近上傳截圖風格的台股分析儀表板，同時要求：
- 不預設綁死 NAS，GitHub 公開後仍要讓非 NAS 使用者可跑
- Dashboard 支援「即時自動報價」與「使用者手動更新」雙模式
- 雲端託管假設（Redis Cloud / Vercel / Railway）要改成 NAS / Docker-first 的自架構思路

### 6.1 為何沒有另開新 repo

本次實作決策是**不另開新 repo**，而是在既有 repo 內新增 dashboard 子應用，理由如下：

1. 現有 repo 已有 FinMind / Fugle / TWSE / MOPS 的可用資料層
2. 既有 Docker、`.env`、MCP、晨報腳本與驗證腳手架可直接復用
3. Dashboard 若拆出去，反而會把資料取得與部署維護分裂成兩套

實際落點：

```
dashboard/
  api/
  web/
```

### 6.2 Phase 0 交付內容

Phase 0 不是畫面，而是把**可運行骨架與資料契約**先確立：

- 新增 `dashboard/api`：
  - `app/main.py`
  - `routers/health.py`
  - `routers/stocks.py`
  - `services/market_data.py`
  - `cache.py`
  - `config.py`
- 新增 `dashboard/web`：
  - React + Vite + TypeScript 基礎骨架
  - 深色高密度 dashboard layout
- 新增跨平台部署 wiring：
  - `docker-compose.yml` 新增 `stock-dashboard-api` / `stock-dashboard-web`
  - `.env.example` 新增 dashboard 相關設定
  - README 新增本機開發與 Docker profile 啟動方式
- 新增測試：
  - `tests/test_dashboard_api.py`

#### Phase 0 核心技術決策

1. **Dashboard 不直接打 MCP schema**
   - 新建 dashboard API/BFF，讓前端只拿 UI 需要的 payload
2. **Phase 1 快取先用 process-local TTL cache**
   - 先不用 Redis / Valkey，降低複雜度
3. **Docker-first，多部署 profile**
   - NAS 是優先場景，但不是唯一場景

### 6.3 Phase 1 交付內容

Phase 1 已交付一個**可運行 MVP**：

- 股票代號輸入
- 股票標頭（名稱 / 代號 / 報價 / 漲跌 / 買賣價 / 量）
- 日 K 主圖
- 成交量子圖
- 更新模式切換：
  - 即時自動報價
  - 使用者手動更新
- 右欄保留後續分析區塊位置

#### Phase 1 API 端點

- `GET /api/health`
- `GET /api/stocks/{stock_id}/quote`
- `GET /api/stocks/{stock_id}/chart`
- `POST /api/stocks/{stock_id}/refresh`

#### Phase 1 與原始規劃的取捨

刻意**沒有**在這一步就做：

- KD / MACD 圖表 panes
- 主力 / 法人圖表
- AI 勝率或明日預測
- 60 分 K

原因是先把：

1. 基礎資料流
2. 佈局骨架
3. 更新模式
4. Docker / NAS 可部署性

先做穩，之後再往上疊分析層。

### 6.4 遇到的實際部署問題：`Failed to fetch`

Henry 在 NAS 上以 `http://192.168.3.33:9080` 開啟 dashboard，輸入 `2330` 後看到 `Failed to fetch`。

#### 問題根因

最初前端預設會直接以：

- `http://<目前主機>:9180`

去打 API。這在同區網瀏覽器情境下會遇到兩類風險：

1. CORS 設定不包含實際使用的來源
2. Browser 直接跨 port 打 API，部署環境容易受網路、反向代理、瀏覽器限制影響

#### 修正方案

改成**同 origin 代理優先**：

- `dashboard/web/nginx.conf` 新增：
  - `location /api/ { proxy_pass http://stock-dashboard-api:9180; }`
- `dashboard/web/src/lib/api.ts`
  - 預設 API base 改為空字串 `""`
  - browser 直接打同 origin `/api/...`
- `dashboard/web/vite.config.ts`
  - 本機開發用 Vite proxy 把 `/api` 轉給 `127.0.0.1:9180`

這個修正比單純補 CORS 更穩，因為 production browser 不再需要直接跨 port 存取 API。

### 6.5 NAS 部署文件補充

另外新增：

- `docs/deploy-nas.md`

內容包含：

- Synology NAS 上的容器啟動步驟
- `.env` 需要填哪些欄位
- `9080 / 9180 / 9123` 的 port 對應
- `docker compose` 常用操作
- 同區網存取時 CORS 該怎麼填
- `9080` 如果撞 port，如何改成 `9090`

### 6.6 Port 調整：Dashboard Web 由 8080 改成 9080

因 Henry 的 NAS 上已有其他容器占用 `8080`，因此把 dashboard web 對外 port 改成：

- `9080:8080`

同步修改：

- `docker-compose.yml`
- `.env.example`
- `README.md`
- `docs/deploy-nas.md`

### 6.7 Phase 2 起手式（本次已開始，不是只規劃）

雖然使用者要求「先記錄 Phase 0 / 1，再 push，接著開始 Phase 2」，本次已直接把 Phase 2 的第一批內容落地，避免 repo 只停在畫面骨架：

- 新增 `GET /api/stocks/{stock_id}/analysis`
- 在 `services/market_data.py` 內加入：
  - 均線（MA5 / MA20 / MA60）
  - 布林通道
  - KD（rolling stochastic 版本）
  - MACD（EMA 版本）
  - 規則式技術總覽
  - 關鍵價位（壓力 / 回檔 / 支撐）
  - 指標總表資料
- 前端右欄改為顯示真實 analysis payload：
  - 技術分析總覽
  - 關鍵價位
  - 指標總表

#### 尚未完成的 Phase 2 項目

目前還沒做完：

- KD / MACD 視覺化子圖
- 真正的指標表格元件
- 關鍵價位圖上標注
- 更完整的 technical summary 文案與規則引擎整理

但 Phase 2 已經不是空轉，後續維護者可以從 `analysis` endpoint 與右欄 UI 接續擴充。

### 6.8 驗證方式

本輪已做的驗證：

- `.venv/bin/python -m pytest -q tests/test_dashboard_api.py`
- `GET /api/health`
- `GET /api/stocks/2330/quote`
- `GET /api/stocks/2330/chart?timeframe=daily&limit=60`
- `GET /api/stocks/2330/analysis`
- `dashboard/web` 的 `npm run build`

#### 限制

在目前 agent 執行環境中，**沒有 `docker` binary**，因此無法直接做：

- `docker compose config`
- 實際容器啟停驗證

因此 Docker 端的有效性是透過：

1. YAML 結構檢查
2. 本機 API / 前端 build 成功
3. NAS 實機回報與部署文件補充

來交叉確認。
**日期**：2026-05-19（初版），2026-05-20（cron 修復）  
**初版產出**：
- `get_tw_market_briefing`：一口氣抓完晨報所需全部資料
- `get_investor_conference_events`：法說會行程
- `get_equity_research_snapshot`：個股研究快照
- `skills/tw-equity-research/SKILL.md`
- `skills/tw-morning-briefing/SKILL.md`
- `skills/tw-earnings-calendar/SKILL.md`

**2026-05-20 修復產出**：
- 晨報腳本修正：用專案 `.venv/bin/python` 而非系統 `python3`（解決 `ModuleNotFoundError`）
- 兩路 cron job 建立：`tw-morning-briefing-0830-discord` + `tw-morning-briefing-0830-line`
- `scripts/send_tw_morning_briefing.sh` 便利腳本

---

### Phase 6：部署、文件、分享
**日期**：2026-05-20  
**產出**：
- `Dockerfile` + `docker-compose.yml`：一鍵容器化
- `docs/DEPLOYMENT.md`：原始英文部署說明
- `docs/DEPLOYMENT-ZH.md`：繁體中文詳解版
- `docs/USAGE.md`：使用說明
- `.env.example`：分享用範本（不含真實 API key）
- Port 全域調整：8000 → 9123

---

### Bug 修復階段（2026-05-21）

**日期**：2026-05-21

9 個 bug 一次性修復，修改後的檔案由 Henry 放置於 `projects/openclaw-financial-tw-debug/`，經 code review 後同步進主目錄。

| Bug 編號 | 嚴重性 | 問題摘要 | 修復方式 |
|---------|--------|---------|---------|
| Bug 1 | 🔴 | `_fetch_json_url` 繞路用假的 `httpx.Response` 再呼叫 `.json()`，且未 import `json` | 改用 `json.loads(content)` |
| Bug 2 | 🔴 | `_load_dotenv()` 每次呼叫 `_finmind_token()` / `_fugle_api_key()` 都重讀一次 `.env` 磁碟 | 加 `_dotenv_loaded: bool = False` 模組級旗標，讀過一次就跳過 |
| Bug 3 | 🔴 | `get_tw_market_briefing` 的 `future.result()` 任一炸掉就讓整個晨報失敗 | 每個 future 個別包 try/except，失敗存 `{"_error": "...", "data": []}` |
| Bug 4 | 🟡 | `get_gdp_data` 預設 `end_time="2025-Q4"` 已過期，2026 年取不到新資料 | 改 `end_time: str | None = None`，動態計算當前季度 |
| Bug 5 | 🟡 | `get_equity_research_snapshot` 8 個 HTTP 請求序列執行（延遲 8 倍）| 改 `ThreadPoolExecutor(max_workers=7)` 並行 |
| Bug 6 | 🟡 | `get_equity_research_snapshot` 固定 `start_date="2026-01-01"` + 缺 `balance_sheet` / `cash_flow_statement` | 改動態 `datetime.now() - timedelta(days=365)`，補齊兩張財報 |
| Bug 7 | 🟠 | `get_exdividend_result`（除權除息結果）在 Plan 和 Skill 文件中用到但從未實作 | 新增 tool，接 FinMind `TaiwanStockDividendResult` |
| Bug 8 | 🟠 | `get_taiex_index`（加權價格指數）未實作，只有 TRI（全益指數）| 新增 tool，接 FinMind `TaiwanStockMarketIndex`，`get_taiex_total_return_index` 保留 |
| Bug 10 | 🟡 | `tw_morning_briefing.py` renderer 未處理 Bug 3 的 partial-error payload，dict/list 判斷也有問題 | 新增 `_safe_data()` / `_error_label()` helpers；`price/close/Close` 三層 fallback；footer 列出所有失敗來源 |
| Bug 11 | 🟡 | 法說會/業績發表會未過濾過期場次（「AI及綠能」（已結束）、「自行車產業」（已結束）仍在簡報中）| 新增 `_parse_event_date_range()` 解析「月 日到月 日」並正確處理跨年（如「12月20日到1月20日」→「2027-01-20」）；`_is_event_expired()` 以 `end_date < 今天` 過濾；`get_investor_conference_events` 統一先做日期過濾再截長度 |

**同步後檔案**：
- `mcp/finmind_server.py` → 完整同步（語法驗證通過）
- `scripts/tw_morning_briefing.py` → 完整同步（語法驗證通過）

---

## 六、現有腳本總覽

| 腳本 | 用途 |
|------|------|
| `scripts/tw_morning_briefing.py` | 晨報生成主程式（排程呼叫）|
| `scripts/send_tw_morning_briefing.sh` | 晨報產出 + Discord/LINE 發送便利包 |
| `scripts/run_finmind_sse.sh` | 啟動 MCP SSE 伺服器 |
| `scripts/ensure_finmind_sse.sh` | 確保 SSE 服務一直活著（定期檢查 + 重啟）|
| `scripts/train_dashboard_models.py` | 離線重訓 dashboard 勝率 / 方向預測模型 |
| `scripts/verify_mcp_finmind.py` | 驗證 FinMind API 可正常讀取 |
| `scripts/verify_mcp_protocol.py` | 驗證 MCP stdio 協定溝通正常 |
| `scripts/verify_mcp_sse.py` | 驗證 SSE 端點可達 |

---

## 七、維護指南

### 7.1 新增一個 MCP Tool

1. 在 `mcp/finmind_server.py` 的 tool 列表中新增 method
2. 在 `mcp_server.add_tool()` decorator 下註冊
3. 用 `scripts/verify_mcp_protocol.py` 確認新 tool 出現在清單
4. 若需要新資料源，先確認 endpoint 可達，再寫進 `helpers/`（統一的 HTTP fetch 介面）

### 7.2 新增一個 Skill

1. 在 `~/.openclaw/workspace/skills/tw-<name>/SKILL.md` 建立 skill
2. 參考現有 skills 的 front-matter 格式（`name`、`description`、`triggers`）
3. `openclaw skills check` 確認新 skill 可見

### 7.3 修改 Port

見上方 4.2 節。建議日後如果有類似的「環境變數綁定」的設定，都用此模式：`.env` 單一來源，Python 讀 `os.getenv`。

### 7.4 更新 cron job

```bash
# 列出所有排程
cron action=list

# 立即觸發測試
cron action=run jobId=<id>

# 查看執行歷史
cron action=runs jobId=<id>
```

### 7.5 資料來源斷線時的處理

各 tools 使用的 helper 已有重試邏輯（HTTP transient error retry）。若某個來源長期失效：
1. 找到對應的 tool
2. 在 helper 或 tool 內加入備援邏輯（參考 Phase 2 重大訊息的 TWSE fallback 模式）

---

## 八、已知限制

| 限制 | 說明 |
|------|------|
| LINE 跨平台驗證 | 在 Discord 綁定的 OpenClaw 會話無法直接實測 LINE 發送，需在 LINE 綁定會話中單獨驗證 |
| FinMind 非商業限制 | 若計畫商業化，需升級付費方案 |
| GDP DGBAS endpoint | 依賴特定的 SDMX pattern，若 DGBAS 改版可能需要重新找 endpoint |
| T+1 資料時間差 | 台股當日收盤資料在收盘后 1~2 小時才更新，晨報並非即時行情 |
| 期貨/選擇權 | FinMind 有覆蓋但本專案目前未實作對應的 skill |
| XBRL 附表 | 尚未實作；目前以 FinMind 主體財報覆蓋主要需求 |

---

## 九、關鍵聯繫人與參考資源

| 項目 | 內容 |
|------|------|
| FinMind | <https://finmindtrade.com/> |
| FinMind llms.txt | <https://finmind.github.io/llms-full.txt> |
| Fugle API | <https://developer.fugle.tw/> |
| TWSE OpenAPI | <https://openapi.twse.com.tw/> |
| MOPS 重大訊息 | <https://mops.twse.com.tw/mops/web/t05sr01_1> |
| CBC 開放資料 | <https://www.cbc.gov.tw/> |
| DGBAS 統計資料 | <https://www.dgbas.gov.tw/> |
| Anthropic financial-services | <https://github.com/anthropics/anthropic-financial-services> |

---

*本文件為內部維護文件，記錄真實開發過程。如有新開發者接手，請同步更新本文檔。*
