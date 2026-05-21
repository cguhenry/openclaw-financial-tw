# OpenClaw × Anthropic Financial Services — 台灣金融市場整合開發規劃

> **版本**：v1.1 　**日期**：2026-05-19（更新：免費資料來源替代 TEJ / CMoney）  
> **目標**：將 `anthropics/financial-services` 以 Skill / MCP 方式落地至 OpenClaw，並擴充台灣市場資料來源與財務分析能力。  
> **v1.1 變更摘要**：以 FinMind（開源）+ Fugle API 替代付費的 TEJ / CMoney，在非商業用途下達成 **零成本** 台灣市場完整資料覆蓋。

---

## 一、專案評估摘要

### 1.1 `anthropics/financial-services` 核心結構

| 層次 | 內容 | 技術形式 |
|------|------|----------|
| **Agents** | 端對端工作流 (Pitch Agent、Earnings Reviewer、Model Builder…) | Markdown system prompt + skills bundled |
| **Skills** | 領域知識模塊 (DCF、LBO、Comps、3-Statement…) | `.md` 技能檔 |
| **Commands** | 明確觸發指令 (`/dcf`, `/comps`, `/earnings`…) | YAML 定義 |
| **Connectors** | 資料提供商 MCP 伺服器 (FactSet、Morningstar、S&P Global…) | `.mcp.json` 設定 |
| **Managed Agents** | 無頭部署 (`agent.yaml` + 子代理) | Claude Managed Agents API |

**License**：Apache 2.0 — 可自由 Fork、修改、商業使用。

### 1.2 OpenClaw 技能架構相容性

| 評估面向 | 結論 |
|----------|------|
| **技能格式** | ✅ 高度相容。兩者皆以 Markdown 撰寫技能，無需編譯步驟。 |
| **MCP 整合** | ✅ OpenClaw 原生支援 MCP Server，`.mcp.json` 可直接掛載。 |
| **指令系統** | ✅ OpenClaw Slash Commands 與 financial-services 的 `/dcf`、`/comps` 格式一致。 |
| **記憶體 / 持久化** | ✅ OpenClaw 的持久記憶可保存使用者的投資組合、偏好設定、分析歷史。 |
| **多管道觸達** | ✅ WhatsApp/Telegram 呼叫 `/earnings 2330` 這類指令完全可行。 |
| **Managed Agents API** | ⚠️ OpenClaw 目前不直接走 Anthropic Managed Agents API；子代理調度需自行橋接或改寫為 OpenClaw 多代理模式。 |
| **Microsoft 365 外掛** | ❌ 與 OpenClaw 無關，可忽略。 |

**整體可行性：高。** 只需將 `plugins/vertical-plugins/` 下的 skill `.md` 搬移至 OpenClaw skill 目錄，調整 YAML front-matter 欄位即可啟用；MCP connector 設定幾乎原封不動。

---

## 二、現有 MCP 連接器的台灣市場覆蓋缺口

### 2.1 現有連接器覆蓋範圍

| 連接器 | 主要覆蓋市場 | 台灣 TWSE/TPEx 覆蓋 |
|--------|------------|---------------------|
| Morningstar | 全球 | 部分（共同基金為主，個股有限）|
| S&P Capital IQ | 北美為主 | 有限（主要上市公司）|
| FactSet | 全球機構 | 有限（需高成本訂閱）|
| LSEG (Refinitiv) | 全球 | 有限（大型藍籌）|
| PitchBook | PE/VC | 幾乎無台灣新創資料 |
| Daloopa | 美股財報 AI 解析 | 無 |
| Moody's | 信評 | 有限 |

**結論**：現有連接器對台灣中小型上市公司、興櫃市場、以及繁體中文財報的支援幾乎空白，需要自建台灣市場 MCP 伺服器。

---

## 三、台灣市場擴充元件設計

### 3.1 需新增的資料來源

#### A. 免費 / 官方開放資料

| 來源 | 資料類型 | API / 存取方式 |
|------|----------|---------------|
| **TWSE 臺灣證券交易所** | 股價、成交量、指數、外資買賣超、融資融券 | `openapi.twse.com.tw` REST API（免費） |
| **TPEx 證券櫃檯買賣中心** | 上櫃/興櫃股票行情 | `www.tpex.org.tw` OpenAPI（免費）|
| **MoPS 公開資訊觀測站** | 財務報告（XBRL）、重大訊息、董事會決議 | `mops.twse.com.tw` XBRL + HTML 抓取 |
| **FSC 金融監督管理委員會** | 法規、裁罰、保險業/銀行業資料 | `www.fsc.gov.tw` 公開資料 |
| **中央銀行** | 匯率（USD/NTD）、利率、M1B/M2 | `www.cbc.gov.tw` 統計資料庫 |
| **主計總處** | GDP、CPI、景氣指標 | `www.dgbas.gov.tw` 統計資料庫 |
| **財政部** | 海關進出口、營業稅 | 政府開放資料平台 `data.gov.tw` |

#### B. 免費開源資料（TEJ / CMoney 的替代方案）⭐ 推薦優先使用

> **結論先說**：FinMind + Fugle API 組合可覆蓋 TEJ/CMoney **85%** 的功能，且完全免費（非商業用途）。

##### FinMind — 開源台股金融資料 API

| 資料面向 | 涵蓋資料集 | 備註 |
|----------|-----------|------|
| **技術面** | 日K/週K/月K、即時快照、歷史 tick（5秒）、PER/PBR、TAIEX 指數 | 每日自動更新 |
| **基本面** | 綜合損益表、現金流量表、資產負債表、月營收、股利政策、除權息結果表 | 財報三表齊全 |
| **籌碼面** | 外資持股比例、股權分散表、融資融券餘額、三大法人買賣明細、借券成交明細、分點進出明細 | CMoney 主力資料完全覆蓋 |
| **衍生性商品** | 期貨/選擇權 daily+即時+tick、三大法人期選買賣、各券商每日交易 | |
| **國際市場** | 美股日K/分K、美債殖利率、G8 匯率與央行利率、黃金/原油價格 | |

**API 存取方式**：
```bash
# Python SDK（推薦）
pip install finmind

# 或直接 REST API
GET https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=2330&start_date=2024-01-01

# AI 整合捷徑：FinMind 提供 llms.txt，可直接餵給 Claude 學習 API 用法
# https://finmind.github.io/llms.txt          ← 精簡版（API 概覽）
# https://finmind.github.io/llms-full.txt     ← 完整版（所有欄位定義+範例）
```

**免費額度**：
| 身分 | 速率限制 |
|------|----------|
| 未登入 | 300 次 / 小時 |
| 免費註冊（email 驗證）| 600 次 / 小時 |
| 付費方案 | 更高額度（有商業授權）|

> ⚠️ **授權注意**：FinMind 免費版僅限**教育、非商業用途**。若 OpenClaw 用於商業服務，需購買 FinMind 付費方案以取得商業授權（費用仍遠低於 TEJ/CMoney）。

##### Fugle（富果）API — 歷史行情 + 即時報價

| 功能 | 免費條件 | 資料範圍 |
|------|----------|----------|
| **歷史日K（2010年起）** | 無需開戶，直接使用 | 全台上市/上櫃股票 |
| **即時報價 + 最佳五檔** | 申請免費 Fugle 帳號，取得 API Key | 盤中即時 |
| **歷史 tick（逐筆）** | 需付費訂閱 | 高頻分析用 |

> Fugle 歷史日K 適合作為 FinMind 的**備援行情來源**，兩者資料格式略有差異但可互補。

##### 免費資源 vs 付費方案 功能對照

| 資料類型 | FinMind 免費 | Fugle 免費 | MoPS/TWSE 官方免費 | TEJ（付費）| CMoney（付費）|
|---------|:-----------:|:----------:|:------------------:|:---------:|:------------:|
| 財報三表（損益/資負/現金流） | ✅ | ❌ | ✅ XBRL | ✅ | ✅ |
| 月營收 | ✅ | ❌ | ✅ | ✅ | ✅ |
| 三大法人買賣超 | ✅ | ❌ | ✅（TWSE） | ✅ | ✅ |
| 融資融券 | ✅ | ❌ | ✅（TWSE） | ✅ | ✅ |
| 股利政策 / 除權息 | ✅ | ❌ | ✅（MoPS） | ✅ | ✅ |
| 股權分散表 | ✅ | ❌ | ✅（TWSE） | ✅ | ✅ |
| 歷史日K（10年+） | ✅ | ✅ | ❌（無歷史）| ✅ | ✅ |
| 即時報價 | ✅（快照）| ✅ | ✅（收盤後）| ✅ | ✅ |
| 期貨 / 選擇權 | ✅ | ❌ | ✅（TAIFEX）| ✅ | 部分 |
| 分點（券商）進出 | ✅ | ❌ | ❌ | ✅ | ✅ |
| **法人預估 EPS（Consensus）** | ❌ | ❌ | ❌ | ✅ **獨有** | ✅ |
| **TCRI 台灣信用評等** | ❌ | ❌ | ❌ | ✅ **獨有** | ❌ |
| 商業授權（免費版） | ⚠️ 非商業 | ✅ | ✅ | ✅ | ✅ |
| **月費** | **NT$0（非商業）** | **NT$0（基本）** | **NT$0** | **NT$3,000–30,000** | **NT$2,000–10,000** |

**真正無法替代的付費功能**：僅有 **法人預估 EPS** 與 **TCRI 信用評等** 是 TEJ 獨有，若你的分析工作流不需要這兩項，免費方案已完全足夠。

#### C. 商業/付費資料（僅在有特定需求時才考慮）

| 來源 | 資料類型 | 建議時機 |
|------|----------|----------|
| **TEJ 台灣經濟新報** | 法人預估 EPS、TCRI 信評、完整歷史財報 | 需要 Consensus Estimate 或信評分析時 |
| **FinMind 付費方案** | FinMind 全功能 + 商業授權 | 商業產品上線後，升級以合規使用 |
| **XQ 嘉實資訊** | 即時報價、技術指標、程式下單 | 需要程式交易下單功能時 |
| **Bloomberg Terminal** | 全球含台灣 | 機構等級研究，成本最高 |

#### D. 台灣特有財務申報格式

- **XBRL iXBRL**：上市公司財報強制以 XBRL 格式申報，MoPS 提供下載
- **IFRSs 財報季別**：Q1（3月底申報）、Q2（8月中）、Q3（11月中）、年報（3月31日）
- **繁體中文原始財報**：需 OCR + NLP 解析，非英文欄位名稱

---

### 3.2 新增 MCP 伺服器規格

#### `mcp-finmind` — FinMind 開源資料伺服器（核心，優先建置）⭐

```yaml
# mcp-finmind/manifest.yaml
name: mcp-finmind
description: >
  FinMind 開源金融 API 連接器，涵蓋台股技術面/基本面/籌碼面 75+ 資料集。
  優先作為財報、籌碼、行情的主要資料來源，替代 TEJ/CMoney。
version: 0.1.0
backend: https://api.finmindtrade.com/api/v4
llms_doc: https://finmind.github.io/llms-full.txt   # AI 可直接讀取 API 文件
tools:
  # 技術面
  - get_stock_price_daily      # 日K（含還原股價）
  - get_stock_price_realtime   # 即時快照（tick snapshot）
  - get_per_pbr                # 個股 PER、PBR 歷史序列
  - get_taiex_index            # 加權/櫃買 指數
  # 基本面（財報三表）
  - get_income_statement       # 綜合損益表（季/年）
  - get_balance_sheet          # 資產負債表（季/年）
  - get_cash_flow_statement    # 現金流量表（季/年）
  - get_month_revenue          # 月營收（每月 10 日更新）
  - get_dividend_policy        # 股利政策（現金股利、股票股利）
  - get_exdividend_result      # 除權除息結果表
  # 籌碼面
  - get_institutional_flows    # 三大法人買賣明細（外資/投信/自營）
  - get_margin_short_sale      # 融資融券餘額
  - get_shareholding_dist      # 股權分散表（大股東持股區間）
  - get_foreign_holding_pct    # 外資持股比例趨勢
  - get_broker_trading         # 分點（券商）進出明細
  - get_short_selling          # 借券成交明細
  # 衍生性商品
  - get_futures_daily          # 期貨每日行情
  - get_options_daily          # 選擇權每日行情
```

#### `mcp-twse` — 台灣股市官方資料伺服器（輔助 / Fallback）

```yaml
# mcp-twse/manifest.yaml
name: mcp-twse
description: >
  TWSE/TPEx 官方 OpenAPI 連接器。作為 mcp-finmind 的備援來源，
  或用於取得 FinMind 尚未整合的官方即時資料。
version: 0.1.0
tools:
  - get_stock_quote          # 即時/收盤報價（股號 → 價量資料）
  - get_historical_prices    # 歷史日/週/月 K 線
  - get_margin_trading       # 融資融券餘額
  - get_institutional_flows  # 外資、投信、自營商買賣超
  - get_twse_index           # 大盤指數、類股指數
  - search_company           # 股票代號/公司名稱搜尋
  - get_tpex_otc_quote       # 上櫃股票行情
  - get_warrant_data         # 權證資料
```

#### `mcp-mops` — 財報與重訊伺服器

```yaml
# mcp-mops/manifest.yaml
name: mcp-mops
description: 公開資訊觀測站財務報告、重大訊息、董監事資料
version: 0.1.0
tools:
  - get_financial_statements # 損益表、資產負債表、現金流量表（季/年）
  - get_xbrl_report          # XBRL 格式財報下載與解析
  - get_major_announcements  # 重大訊息（即時）
  - get_dividends            # 股利政策與發放紀錄
  - get_shareholding         # 大股東持股、董監持股
  - get_ownership_structure  # 股權結構圖
  - get_related_party_txns   # 關聯人交易揭露
```

#### `mcp-cbc-macro` — 台灣總經資料伺服器

```yaml
# mcp-cbc-macro/manifest.yaml
name: mcp-cbc-macro
description: 中央銀行、主計總處、財政部總體經濟資料
version: 0.1.0
tools:
  - get_usd_ntd_rate         # 美元/台幣匯率（即時/歷史）
  - get_interest_rates       # 重貼現率、基準利率
  - get_money_supply         # M1B、M2 貨幣供給
  - get_gdp_data             # GDP 成長率、季增/年增
  - get_cpi_ppi              # 通膨指標
  - get_trade_balance        # 進出口貿易數據
  - get_pmi                  # 採購經理人指數
```

---

### 3.3 台灣市場專屬 Skills（技能模塊）

#### 核心財務分析技能

| 技能名稱 | 指令 | 功能描述 |
|----------|------|----------|
| `tw-financial-statements` | `/twfs` | 解析繁體中文 IFRS 財報，自動對應至標準化英文欄位 |
| `tw-dcf-model` | `/twdcf` | 台灣版 DCF：使用 NTD 計算、台灣無風險利率（10Y公債殖利率）、台股 ERP |
| `tw-comps` | `/twcomps` | TWSE/TPEx 同類股比較（本益比、股價淨值比、EV/EBITDA）|
| `tw-earnings-analysis` | `/twearnings` | 財報季分析：EPS、毛利率趨勢、法說會重點摘要 |
| `tw-dividend-analysis` | `/twdiv` | 現金殖利率、股利成長、配息穩定性分析 |
| `tw-sector-overview` | `/twsector` | 台灣半導體/電子/金融/傳產/生技 產業結構分析 |
| `tw-chip-analysis` | `/twchip` | 籌碼面：三大法人、融資比率、大股東異動 |

#### 台灣特有估值調整技能

| 技能名稱 | 功能描述 |
|----------|----------|
| `tw-risk-adjustments` | 加入台海地緣政治風險溢價、半導體景氣循環調整至 DCF 折現率 |
| `tw-supply-chain-map` | 台灣科技股供應鏈關係圖（上下游廠商關聯）|
| `tw-regulatory-check` | FSC 法規合規查核（金控、保險、銀行業適用）|
| `tw-holding-structure` | 台灣投資控股結構解析（交叉持股常見問題）|

---

## 四、DCF 估值模型台灣化調整

### 4.1 折現率參數 — 台灣市場基準

```
WACC 計算：
  無風險利率 (Rf)     = 台灣 10 年期公債殖利率（中央銀行資料）
  股票風險溢價 (ERP)   = 台灣歷史 ERP ≈ 6.0–7.5%（Damodaran NYU 提供亞洲數據）
  Beta               = 相對台灣加權指數 (TAIEX) 計算
  信用利差           = 公司信評（若無，參考同業平均）
  
  台幣特殊考量：
    - 匯率風險：對美元匯率波動（對出口導向企業影響大）
    - 台海地緣政治風險溢價：+0.5–2.0%（依分析師判斷加入）
```

### 4.2 現金流預測台灣化

```
財報期別：
  Q1：1–3月（5月15日申報截止）
  Q2：1–6月（8月14日申報截止）
  Q3：1–9月（11月14日申報截止）
  年報：1–12月（隔年3月31日申報截止）

特殊科目對應：
  - 「業外損益」→ Non-operating income/expense
  - 「研究發展費用」→ R&D expense（科技業常見高比例）
  - 「員工分紅費用化」→ 台灣特有：Employee bonuses expensed
  - 「其他綜合損益」→ OCI（匯兌換算調整重要）
```

### 4.3 台灣版 `/twdcf` 技能流程

```
Step 1: 取得標的公司代號 → mcp-mops 抓取近 3 年財報（XBRL）
Step 2: mcp-cbc-macro 取得當前 10Y 公債殖利率作為 Rf
Step 3: 計算歷史 Beta（相對 TAIEX，36 個月月報酬）
Step 4: 建立 5 年 FCF 預測（含用戶輸入假設或自動推算）
Step 5: 計算 WACC（含台海風險溢價選項）
Step 6: Gordon Growth Model 計算終值（台灣 GDP 長期成長率 ≈ 2–3%）
Step 7: 折現、敏感度分析矩陣（WACC ± 1%，Terminal Growth ± 0.5%）
Step 8: 輸出 NTD 與 USD 雙幣別估值
```

---

## 五、整合架構圖

```
┌─────────────────────────────────────────────────┐
│                  OpenClaw Agent                  │
│  (WhatsApp / Telegram / Discord / CLI)           │
└────────────┬────────────────────────────────────┘
             │ 呼叫技能 / 指令
             ▼
┌─────────────────────────────────────────────────┐
│              Skill Layer（技能層）                │
│                                                  │
│  ┌──────────────────┐  ┌──────────────────────┐ │
│  │ 原版 Skills（移植）│  │ 台灣擴充 Skills（新增）│ │
│  │ /dcf  /comps     │  │ /twdcf  /twcomps     │ │
│  │ /earnings  /lbo  │  │ /twearnings  /twchip │ │
│  │ /ic-memo  /screen│  │ /twfs  /twdiv        │ │
│  └────────┬─────────┘  └──────────┬───────────┘ │
└───────────┼──────────────────────┼──────────────┘
            │ MCP Tool Calls        │
            ▼                       ▼
┌───────────────────┐   ┌────────────────────────────────────────┐
│ 現有 MCP 連接器    │   │ 新增台灣 MCP 伺服器                      │
│ (全球市場)         │   │                                        │
│ - Morningstar     │   │ ⭐ mcp-finmind（主力，免費開源）          │
│ - FactSet         │   │   ├─ FinMind API（75+ 台股資料集）        │
│ - S&P Capital IQ  │   │   ├─ 技術面：日K/即時/PER/PBR            │
│ - LSEG            │   │   ├─ 基本面：財報三表/月營收/股利          │
│ - PitchBook       │   │   └─ 籌碼面：法人/融資券/股權分散/分點     │
│ - Moody's         │   │                                        │
│ - MT Newswires    │   │ mcp-fugle（歷史行情 + 即時，免費）         │
│ - Aiera           │   │   └─ 歷史日K（2010起）/ 即時快照          │
└───────────────────┘   │                                        │
                        │ mcp-mops（財報 XBRL，官方免費）           │
                        │   ├─ 公開資訊觀測站 XBRL 財報             │
                        │   └─ 重大訊息 RSS                        │
                        │                                        │
                        │ mcp-twse（官方行情，免費 / Fallback）      │
                        │   └─ TWSE / TPEx OpenAPI               │
                        │                                        │
                        │ mcp-cbc-macro（總經，免費）               │
                        │   ├─ 中央銀行統計資料庫                   │
                        │   └─ 主計總處 GDP/CPI                    │
                        │                                        │
                        │ mcp-tej（選配，需付費）                   │
                        │   └─ 法人預估 EPS / TCRI 信評（獨有）     │
                        └────────────────────────────────────────┘

資料層優先順序（Fallback Chain）：
  財報三表：FinMind → MoPS XBRL → MoPS HTML scraping
  行情歷史：FinMind → Fugle API → yfinance（最後備援）
  籌碼面：FinMind → TWSE OpenAPI
  即時報價：Fugle 即時 API → TWSE OpenAPI（收盤後）
```

---

## 六、開發階段規劃

### Phase 0 — 環境建置與評估（第 1–2 週）

**目標**：確認 OpenClaw 環境、Fork 並試裝財務技能。

- [ ] Fork `anthropics/financial-services` 到自己的 GitHub
- [ ] 安裝 OpenClaw（Hackable 模式，從 source 執行）
- [ ] 試裝 `financial-analysis` 垂直插件（核心技能）
- [ ] 驗證 `/dcf`, `/comps`, `/earnings` 指令在 OpenClaw 中正常觸發
- [ ] 評估現有 MCP 連接器（Morningstar/FactSet）對台股的實際覆蓋率
- [ ] **註冊 FinMind 帳號**（免費，email 驗證後取得 token，速率上限提升至 600/hr）
  - 官網：`https://finmindtrade.com/`
  - 取得 API Token → 存入 OpenClaw `.env`
- [ ] **申請 Fugle 免費帳號**，取得歷史行情 API Key
  - 官網：`https://developer.fugle.tw/`
- [ ] 確認 TWSE OpenAPI 存取正常（無需帳號）
- [ ] 用 FinMind `llms-full.txt` 快速盤點可用資料集（直接貼給 Claude 詢問）

**交付物**：環境確認報告、缺口分析清單

---

### Phase 1 — `mcp-finmind` 核心資料伺服器（第 3–5 週）⭐ 優先建置

**目標**：以 FinMind 為主力後端，建立台股技術面、基本面、籌碼面一站式 MCP 伺服器。

**技術規格**：
```
語言：Python 3.12 + FastAPI
MCP 協議：mcp Python SDK (anthropic-mcp)
後端：FinMind Python SDK (pip install finmind) + REST API
部署：本機 Docker / 或使用者 VPS
```

**開發任務**：
- [ ] 安裝 FinMind SDK：`pip install finmind`
- [ ] 以 FinMind token 初始化 `DataLoader`，驗證 600 次/小時速率
- [ ] 實作 MCP tools（財報三表）：
  ```python
  # 範例：取得台積電近 8 季損益表
  from FinMind.data import DataLoader
  dl = DataLoader()
  dl.login_by_token(api_token=os.getenv("FINMIND_TOKEN"))
  df = dl.taiwan_stock_financial_statement(
      stock_id="2330", start_date="2022-01-01"
  )
  ```
- [ ] 實作 MCP tools（籌碼面）：`get_institutional_flows`, `get_margin_short_sale`, `get_broker_trading`
- [ ] 實作 MCP tools（行情）：`get_stock_price_daily`, `get_per_pbr`, `get_month_revenue`
- [ ] 實作快取層（SQLite / Redis），避免重複呼叫相同資料集
  - 財報資料：TTL 24 小時（季報不常變）
  - 日K/籌碼：TTL 收盤後更新（16:00 後刷新）
  - 即時快照：TTL 30 秒
- [ ] 撰寫 OpenClaw `.mcp.json` 設定，掛載 mcp-finmind
- [ ] 整合測試：
  - `get_institutional_flows("2330")` → 台積電三大法人買賣超
  - `get_income_statement("2454", "2023-01-01")` → 聯發科歷年損益表
  - `get_dividend_policy("2330")` → 台積電股利政策

**FinMind rate limit 應對策略**：
- 快取層優先，同一資料集當日不重複請求
- 批次查詢多檔股票時使用 `use_async=True` 參數
- 超過限制時自動 fallback 至 TWSE OpenAPI（官方來源）

---

### Phase 1.5 — `mcp-fugle` 歷史行情 + 即時報價（第 5 週，可與 Phase 1 並行）

**目標**：補強 FinMind 即時報價不足之處，以 Fugle API 提供穩定的歷史/即時行情。

- [ ] 申請 Fugle 免費 API Key（開發者後台：`developer.fugle.tw`）
- [ ] 實作 `get_historical_ohlcv(stock_id, start, end)` — 歷史日K（2010年起）
- [ ] 實作 `get_realtime_quote(stock_id)` — 即時報價 + 最佳五檔
- [ ] 設定為 mcp-finmind 的行情備援（Fallback Chain）
- [ ] 整合測試：與 FinMind 同股同期資料交叉比對，確認價格一致

---

### Phase 2 — `mcp-mops` 財報深度解析伺服器（第 6–8 週）

**目標**：補強 FinMind 基本面資料在**附表、附註、重大訊息**等非結構化部分的缺口，並提供 XBRL 原始格式存取。

> 注意：財報三表主體（損益/資產負債/現金流）已由 `mcp-finmind` 覆蓋，本 Phase 聚焦 FinMind **尚未整合**的資料。

**開發任務**：
- [ ] XBRL 解析器：讀取 MoPS 提供的 iXBRL 財報**附表**（關聯人交易、分部資訊等）
  - 使用 `arelle` 工具解析
  - 繁中標籤對應 IFRS 標準英文欄位（參見附錄 B）
- [ ] `get_major_announcements`：重大訊息 RSS 訂閱解析
  - MoPS RSS：`https://mops.twse.com.tw/mops/web/rss`
  - 分類篩選：法說會、董事會決議、轉投資、買回庫藏股
- [ ] `get_shareholding`：大股東/董監事持股（MoPS 每季揭露）
- [ ] `get_related_party_txns`：關聯人交易揭露（XBRL 附表）
- [ ] `get_ownership_structure`：投資控股結構（台灣交叉持股常見）
- [ ] 測試：台積電(2330)、聯發科(2454)、鴻海(2317) 附表完整解析

**技術挑戰**：
- XBRL 格式有版本差異（舊財報可能只有 HTML/PDF，需降級處理）
- 部分子附表需要 HTML scraping（非 XBRL 結構化）
- 合併財報 vs 個別財報的區別處理

---

### Phase 3 — 台灣版核心技能移植（第 7–10 週）

**目標**：建立台灣市場版財務分析技能，並整合至 OpenClaw。

**任務**：
- [ ] 將 `dcf-model` skill 複製為 `tw-dcf-model`
  - 修改：使用 NTD、台灣公債殖利率（`mcp-cbc-macro`）、TAIEX Beta
  - 資料來源：`mcp-finmind` 取得歷史日K 計算 Beta
  - 新增：台海地緣政治風險溢價參數（預設 1.0%，可調整）
  - 新增：員工股票分紅攤薄效果計算
- [ ] 將 `comps-analysis` 複製為 `tw-comps`
  - 資料來源改為 `mcp-finmind`（PER/PBR 歷史、財報三表）
  - 新增台灣常用估值倍數：殖利率、ROE、PBR
- [ ] 建立 `tw-chip-analysis` (籌碼分析) — 資料來源：`mcp-finmind`
  - 三大法人連續買賣超天數（`get_institutional_flows`）
  - 融資餘額變化率（`get_margin_short_sale`）
  - 外資持股比例趨勢（`get_foreign_holding_pct`）
  - 分點主力進出（`get_broker_trading`）— FinMind 獨有，TEJ 等級資料
- [ ] 建立 `tw-earnings-analysis`
  - EPS YoY/QoQ 成長率（`mcp-finmind` 損益表）
  - 毛利率/營益率/淨利率趨勢
  - 月營收年增率（`get_month_revenue`）
  - 法說會重點（來源：MoPS 法說會簡報 PDF）
- [ ] 建立 `tw-financial-statements` 繁中財報解讀器
- [ ] 完成 OpenClaw 技能目錄整合與 `/tw*` 指令綁定

---

### Phase 4 — 總經資料與產業分析（第 10–12 週）

**目標**：建立台灣總體經濟與產業分析能力。

- [ ] `mcp-cbc-macro`：串接央行、主計總處統計資料庫
- [ ] `tw-sector-overview` 技能：
  - 台灣半導體（IC設計、晶圓代工、封測）供應鏈地圖
  - 電子代工、PCB、被動元件產業分析框架
  - 金融業（金控、銀行、壽險）特殊估值方法（P/B、RoE-g/Ke-g）
  - 生技醫療業（License deal、FDA管線估值）
- [ ] 台灣與全球指數相關性分析（費半指數、台股關係）
- [ ] 電子業景氣循環指標整合（SEMI Book-to-Bill）

---

### Phase 5 — 進階功能與 Agent 整合（第 13–16 週）

**目標**：完成端對端台灣金融 Agent，支援複雜分析工作流。

- [ ] **`tw-equity-research` Agent**：
  - 輸入股票代號 → 自動產出一份完整研究報告（含財報分析、DCF、Comps、投資建議）
  - 輸出格式：Markdown 報告 / PDF / Excel 財務模型
- [ ] **`tw-morning-briefing` Agent**：
  - 每日 08:30 自動推送：大盤指數、前日三大法人、重大訊息、美股夜盤影響
  - 推送管道：WhatsApp / Telegram（OpenClaw 原生支援）
- [ ] **`tw-earnings-calendar` Agent**：
  - 追蹤追蹤清單股票的法說會與財報申報日期
  - 財報發布後自動觸發 `tw-earnings-analysis`
- [ ] **多代理協作**（進階）：
  - 台灣版 `market-researcher` 子代理協調 `mcp-twse`、`mcp-mops`、`mcp-cbc-macro`
- [ ] ClawHub 技能包發布（開源回饋社群）

---

### Phase 6 — 合規、測試與生產部署（第 16–20 週）

- [ ] 法規遵循說明文件（DISCLAIMER：非投資建議、符合 FSC 相關揭露規範）
- [ ] 台灣投信法規查核：若涉及基金，需確認「投顧業務」法規邊界
- [ ] 單元測試、整合測試（覆蓋率 ≥ 80%）
- [ ] 資料精確度驗證（與 Yahoo Finance 台灣、元大/富邦 API 交叉比對）
- [ ] 效能優化（MCP server 回應時間 < 1秒，財報解析 < 5秒）
- [ ] 安全性：API key 管理（OpenClaw `.env`），敏感資料不入記憶體
- [ ] Docker Compose 一鍵部署包（含 mcp-twse + mcp-mops + mcp-cbc-macro）

---

## 七、技術棧建議

| 層次 | 技術選擇 | 理由 |
|------|----------|------|
| MCP 伺服器語言 | Python 3.12 | `anthropic-mcp` SDK 最成熟，XBRL 解析生態豐富 |
| XBRL 解析 | `arelle` 或 `python-xbrl` | 業界標準 XBRL 工具 |
| 快取 | Redis 7 | 高效 K-V 快取，支援 TTL |
| 資料儲存 | PostgreSQL + TimescaleDB | 時序財務資料最佳化 |
| 排程 | OpenClaw heartbeat / Cron | 定期財報/行情抓取 |
| 測試 | pytest + pytest-asyncio | 非同步 MCP 工具測試 |
| 容器化 | Docker + Docker Compose | 本地或 VPS 一鍵部署 |
| 監控 | Prometheus + Grafana | API 呼叫次數、錯誤率監控 |

---

## 八、成本估算

### 開發時間（單人全端開發者）

| 階段 | 工時估算 |
|------|----------|
| Phase 0 評估建置 | 20 小時 |
| Phase 1 mcp-twse | 60 小時 |
| Phase 2 mcp-mops | 80 小時 |
| Phase 3 台灣技能 | 60 小時 |
| Phase 4 總經資料 | 40 小時 |
| Phase 5 進階 Agent | 80 小時 |
| Phase 6 測試部署 | 40 小時 |
| **合計** | **≈ 380 小時（約 10–13 週全職）** |

### 資料來源成本（月費）

| 來源 | 費用 | 用途 |
|------|------|------|
| TWSE / TPEx OpenAPI | **免費** | 官方行情 fallback |
| MoPS 公開資訊觀測站 | **免費** | XBRL 財報附表、重大訊息 |
| 央行 / 主計總處 | **免費** | 利率、匯率、GDP/CPI |
| **FinMind（非商業）** | **免費** | ⭐ 主力資料來源（財報三表、籌碼、行情）|
| **Fugle API（基本）** | **免費** | 歷史日K（2010起）、即時報價 |
| FinMind 付費方案（商業用途時升級）| 詳洽官網 | 解除非商業限制，費用遠低於 TEJ |
| TEJ 台灣經濟新報（有特定需求才考慮）| NT$3,000–30,000/月 | 法人預估 EPS、TCRI 信評（獨有）|
| Claude API（OpenClaw 後端） | 依使用量 | LLM 推理 |

**免費方案總成本：NT$0 / 月（非商業用途），功能覆蓋率達 85%+。**

---

## 九、風險與對策

| 風險 | 嚴重度 | 對策 |
|------|--------|------|
| **FinMind 免費版速率限制（600次/hr）** | 中 | 快取層優先；批次非同步查詢（`use_async=True`）；超限自動 fallback 至 TWSE OpenAPI |
| **FinMind 非商業授權限制** | 高（商業場景）| 商業上線前升級 FinMind 付費方案；或改以 TWSE/MoPS 官方來源重建資料管道 |
| **FinMind 服務中斷或停止維護** | 中 | 資料管道設計雙來源：FinMind 為主，TWSE OpenAPI + MoPS 為備援 |
| Fugle API 方案調整 | 低 | Fugle 行情僅作 fallback；主要行情已由 FinMind 覆蓋 |
| TWSE/TPEx API 變更或速率限制 | 低（已降為備援）| 作為第三層 fallback，影響較小 |
| MoPS XBRL 格式舊版不一致 | 高 | 舊財報降級為 HTML scraping + PDF OCR；主要財報三表已由 FinMind 覆蓋 |
| 繁中財報科目對應錯誤 | 高 | 建立完整對照表並人工驗證前 20 大市值公司 |
| 台海地緣政治風險溢價主觀性 | 低 | 設為使用者可調整參數，提供歷史範圍參考 |
| Anthropic financial-services 上游更新 | 低 | Fork 後追蹤 upstream，定期 merge |
| OpenClaw 架構更新破壞技能格式 | 中 | 鎖定版本，關注 OpenClaw changelog |
| 法規風險（投顧業務界定） | 中 | 加入強制免責聲明，明確定位為「輔助工具，非投資建議」|

---

## 十、里程碑與驗收標準

| 里程碑 | 時間 | 驗收標準 |
|--------|------|----------|
| M1: 環境就緒 | W2 | `/dcf AAPL` 在 OpenClaw 正常執行；FinMind token 已設定 |
| M2: FinMind MCP 上線 | W5 | `get_institutional_flows("2330")` 回傳台積電三大法人買賣超；`get_income_statement("2330")` 回傳近 8 季損益表 |
| M3: 完整籌碼技能 | W7 | `/twchip 2330` 輸出外資持股趨勢、融資比率、分點主力明細 |
| M4: 台灣版 DCF | W10 | `/twdcf 2454` 輸出聯發科 DCF 估值（含敏感度矩陣，資料來源：FinMind）|
| M5: 完整研究報告 | W14 | Telegram 中輸入股號 → 自動產出完整研究報告 PDF |
| M6: 生產部署 | W20 | Docker Compose 一鍵部署，覆蓋率測試通過；若商業使用，FinMind 付費方案已啟用 |

---

## 附錄 A：重要台灣金融資料 API 端點

### FinMind API（主力資料來源）

```python
# === Python SDK（推薦）===
from FinMind.data import DataLoader
import os

dl = DataLoader()
dl.login_by_token(api_token=os.getenv("FINMIND_TOKEN"))

# 損益表（近 8 季）
income = dl.taiwan_stock_financial_statement(stock_id="2330", start_date="2022-01-01")

# 現金流量表
cashflow = dl.taiwan_stock_cash_flows_statement(stock_id="2330", start_date="2022-01-01")

# 月營收
revenue = dl.taiwan_stock_month_revenue(stock_id="2330", start_date="2024-01-01")

# 三大法人買賣超
inst = dl.taiwan_stock_institutional_investors(stock_id="2330", start_date="2024-01-01")

# 融資融券
margin = dl.taiwan_stock_margin_purchase_short_sale(stock_id="2330", start_date="2024-01-01")

# 股權分散表
dist = dl.taiwan_stock_shareholding(stock_id="2330", start_date="2024-10-01")

# 股利政策
div = dl.taiwan_stock_dividend(stock_id="2330")

# 歷史日K（含還原股價）
price = dl.taiwan_stock_daily(stock_id="2330", start_date="2020-01-01")

# 個股 PER/PBR 歷史
perpbr = dl.taiwan_stock_per_pbr(stock_id="2330", start_date="2024-01-01")

# 分點（券商）進出
broker = dl.taiwan_stock_trading_daily_report(stock_id="2330", start_date="2024-01-01")
```

```bash
# === REST API（直接呼叫）===
# 損益表
GET https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockFinancialStatements&data_id=2330&start_date=2022-01-01&token=YOUR_TOKEN

# 三大法人
GET https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id=2330&start_date=2024-01-01&token=YOUR_TOKEN

# AI 整合文件（直接貼給 Claude 使用）
GET https://finmind.github.io/llms.txt          # 精簡版
GET https://finmind.github.io/llms-full.txt     # 完整版（含所有欄位定義）
```

### Fugle API（歷史行情 + 即時報價）

```python
# === Python SDK ===
# pip install fugle-marketdata
from fugle_marketdata import RestClient

client = RestClient(api_key=os.getenv("FUGLE_API_KEY"))

# 歷史日K（candlesticks）
candles = client.stock.historical.candles(**{
    "symbol": "2330",
    "from": "2020-01-01",
    "to": "2026-05-19",
    "timeframe": "D"
})

# 即時報價快照
quote = client.stock.intraday.quote(symbol="2330")
```

### TWSE OpenAPI（官方 Fallback）

```bash
# 個股當日行情
GET https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY?response=json&date=20260519&stockNo=2330

# 三大法人買賣超（全市場）
GET https://openapi.twse.com.tw/v1/fund/T86

# 上市股票清單
GET https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
```

### MoPS 公開資訊觀測站（財報附表 / 重大訊息）

```bash
# XBRL 財報下載（台積電 2024 Q4 合併財報）
GET https://mops.twse.com.tw/server-java/t164sb01?step=1&CO_ID=2330&SYEAR=2024&SSEASON=4&REPORT_ID=C

# 重大訊息 RSS
GET https://mops.twse.com.tw/mops/web/rss
```

### 央行 / 總經資料

```bash
# 央行利率
GET https://www.cbc.gov.tw/public/data/economic/opendata/interest.json

# 美元/台幣匯率
GET https://www.cbc.gov.tw/public/data/economic/opendata/exchangerate.json
```

---

## 附錄 B：台灣財報科目對照（部分）

| 繁體中文科目 | 英文 | IFRS 代碼 |
|------------|------|-----------|
| 營業收入淨額 | Net Revenue | IAS18.Revenue |
| 營業毛利 | Gross Profit | - |
| 推銷費用 | Selling Expenses | IAS1.SG&A |
| 管理費用 | General & Administrative | IAS1.SG&A |
| 研究發展費用 | R&D Expenses | IAS38 |
| 營業利益 | Operating Income | EBIT |
| 業外收入及支出 | Non-operating Income | - |
| 稅前淨利 | Income Before Tax | EBT |
| 所得稅費用 | Income Tax Expense | IAS12 |
| 本期淨利 | Net Income | - |
| 母公司業主淨利 | Net Income attributable to Parent | - |
| 基本每股盈餘 | Basic EPS | IAS33 |
| 不動產廠房及設備 | PP&E | IAS16 |
| 使用權資產 | Right-of-Use Assets | IFRS16 |
| 遞延所得稅資產 | Deferred Tax Assets | IAS12 |
| 應付帳款 | Accounts Payable | - |
| 租賃負債 | Lease Liabilities | IFRS16 |
| 員工福利費用 | Employee Benefits | IAS19 |

---

## 附錄 C：FinMind 台灣市場資料集索引（75+ 個）

主要資料集名稱（用於 REST API `dataset` 參數）：

| 類型 | 資料集名稱 |
|------|-----------|
| 技術面 | `TaiwanStockPrice`, `TaiwanStockPriceAdj`, `TaiwanStockPriceTick`, `TaiwanStockPer`, `TaiwanStockInfo` |
| 基本面 | `TaiwanStockFinancialStatements`, `TaiwanStockBalanceSheet`, `TaiwanStockCashFlowsStatement`, `TaiwanStockMonthRevenue`, `TaiwanStockDividend`, `TaiwanStockDividendResult` |
| 籌碼面 | `TaiwanStockInstitutionalInvestorsBuySell`, `TaiwanStockMarginPurchaseShortSale`, `TaiwanStockShareholdingDist`, `TaiwanStockHoldingSharesPer`, `TaiwanStockTradingDailyReport` |
| 衍生品 | `TaiwanFuturesDaily`, `TaiwanOptionDaily`, `TaiwanFuturesInstitutionalInvestors` |

> 完整清單與欄位定義：`https://finmind.github.io/llms-full.txt`

---

*本文件依 Apache 2.0 授權，可自由修改與分發。*  
*最後更新：2026-05-19 v1.1（新增 FinMind/Fugle 免費資料方案）。建議每季檢視一次以反映 API 及 OpenClaw 架構變化。*
