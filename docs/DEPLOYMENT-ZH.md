# OpenClaw Financial TW 部署與使用說明書

> 本文件為原文 [DEPLOYMENT.md](./DEPLOYMENT.md) 之中文譯註版，針對台灣使用者情境增加詳細解說。

---

## 一、這套系統是什麼？

本專案屬於「多層次架構」，由三個部分組成：

| 層次 | 所在位置 | 用途 |
|------|---------|------|
| **技能層（Skill）** | `~/.openclaw/workspace/skills/tw-*` | 讓 OpenClaw AI 能理解並執行台灣股市相關任務 |
| **MCP 伺服器** | `mcp/finmind_server.py` | 負責實際抓取台灣證券交易所、公開資訊觀測站、央行總經數據 |
| **自動化腳本** | `scripts/tw_morning_briefing.py` | 每日的晨間簡報自動產出與發送 |

Docker（`docker-compose`）只是用來把「上述三層」包成一個獨立的服務，目的是把你的 OpenClaw 主環境和這個股市服務的 Python 套件版本分開，避免衝突。**Docker 不是另一套系統，而是另一種部署方式的包裝。**

---

## 二、兩種部署模式

### 模式 A：在 OpenClaw 機器上直接運行（建議多數人使用）

適用對象：你的 NAS 已經在跑 OpenClaw，不需要另外架一個獨立的容器服務。

#### 前置需求

- Python 虛擬環境已建好在 `projects/openclaw-financial-tw/.venv`
- `.env` 檔案中有 `FINMIND_TOKEN`（台灣股市資料的 API 金鑰，向 [FinMind](https://finmindtrade.com/) 免費申請）
- 可選：`FUGLE_API_KEY`（用於即時股價的備援查詢）

#### 啟動 MCP SSE 伺服器

```bash
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/run_finmind_sse.sh
```

> 這行指令啟動了一個「長期運行的本地網路服務」，監聽在 `http://127.0.0.1:9123/sse`，讓 OpenClaw 可以即時查詢台灣股市資料。

#### 確保它一直活著（防止當機）

```bash
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/ensure_finmind_sse.sh
```

> 這會定期檢查上述服務是否還在執行，若發現停了就自動重啟。建議搭配系統服務（systemd）或 NAS 上的排程工具，達到開機自動啟動。

#### 驗證一切正常

```bash
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_sse.py
```

> 執行後顯示 `SSE endpoint reachable` 就代表成功。

---

### 模式 B：Docker Compose（適合想要完全隔離環境的人）

#### 前置需求

- 已安裝 Docker 與 `docker compose`
- 已複製 `.env.example` 並填入 `FINMIND_TOKEN`

#### 步驟

```bash
cd /home/node/.openclaw/workspace/projects/openclaw-financial-tw
cp .env.example .env          # 複製範本
# 用文字編輯器打開 .env，填入 FINMIND_TOKEN
docker compose up -d --build  # 編譯並啟動容器
```

#### 查看狀態

```bash
docker compose ps                                    # 看容器是否在跑
docker compose logs --tail=100 finmind-tw-mcp       # 看最近 100 行錯誤訊息
```

#### 容器對外暴露的網址

| 端點 | 用途 |
|------|------|
| `http://127.0.0.1:9123/sse` | SSE 即時查詢（主要）|
| `http://127.0.0.1:9123/mcp` | MCP 協定的另一種接入點 |

#### 多客戶端 / 區域網路連線（模式 B）

**預設架構的限制**：Docker 容器內的 MCP 伺服器預設綁定在 `127.0.0.1`，只有同一台機器的程式可以連線，區域網路內的其他 OpenClaw 客戶端無法直接連入。

如果你的使用情境是**讓同一網域內的多台 OpenClaw 實例共享同一個 MCP 容器**，需要做以下三個調整：

**調整 1：讓 MCP 伺服器監聽所有網卡**

在你的 `.env` 檔案（不是 `.env.example`）中加入：

```dotenv
MCP_HOST=0.0.0.0
```

這會讓容器內的 MCP 服務不再只綁定 localhost，而是監聽所有網路介面。

**調整 2：在各客戶端機器的 `openclaw.json` 裡指向主機 IP**

在每台想要連線的客戶端 OpenClaw 的 `~/.openclaw/openclaw.json` 中，填入「執行 Docker 的那台機器的區域網路 IP」：

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

**調整 3：更新 `docker-compose.yml` 的 port binding**

確認 `docker-compose.yml` 的 port 對應有綁在 `0.0.0.0`：

```yaml
ports:
  - "0.0.0.0:9123:9123"
```

```

> **安全提醒**：綁定 `0.0.0.0` 會讓 MCP 服務暴露在你的整個區域網路中。如果NAS所在網路是辦公室或多人共享環境，建議加上防火牆規則或改用 VPN，否則同一網域內任何人都能查詢你的台股資料。個人家庭網路且 NAS 在路由器 NAT 後方，風險較低。

---

## 三、OpenClaw MCP 註冊設定

> **重要提醒**：不論是模式 A 或模式 B，**都必須在 `openclaw.json` 裡註冊這個 MCP 伺服器**。差別只在於 SSE 伺服器是直接跑在 NAS 主機上（模式 A）還是包在 Docker 裡（模式 B）；從 OpenClaw 的視角來看，都是透過同一個 SSE 網址存取，設定完全相同。

**設定位置**：`~/.openclaw/openclaw.json`（在 `mcpServers` 區塊下新增）

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

**啟用並驗證：**

```bash
openclaw config validate
openclaw gateway restart
```

> **模式 B 多機器連線的讀者**：若你計畫讓同一區域網路內的多台 OpenClaw 連到同一個 Docker 容器，請繼續閱讀下方「多客戶端 / 區域網路連線」章節，需要進行額外設定。

---

## 四、晨間簡報自動發送的兩種方式

### 方式一：手動觸發（快速測試用）

```bash
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/send_tw_morning_briefing.sh
```

這支腳本會依序執行：
1. 啟用專案虛擬環境（`.venv`）
2. 抓取當日大盤、三大法人、美股夜盤、重大訊息
3. 讀取 `.env` 裡的 `TW_MORNING_DELIVERIES` 設定
4. 分別對 Discord 和 LINE 發送

#### 必要設定（`.env`）

```dotenv
TW_MORNING_DELIVERIES=discord:user:你的Discord用戶ID,line:你的LINE用戶ID
TW_MORNING_ANNOUNCEMENT_LIMIT=8     # 重大訊息最多顯示幾則
TW_MORNING_TIMEOUT_SECONDS=180     # 整個流程最多等幾秒
```

> **如何找到你的 Discord 用戶 ID？** 在 Discord 開啟「開發者模式」→ 點擊自己的用戶名 → 複製 ID數字。格式為 `user:768728802070626334`。
> **如何找到你的 LINE 用戶 ID？** 在 LINE 开发者后台或通过机器人接口获取，格式为 `U6471476a34c92577e2ac7814f27b8b28`。

---

### 方式二：排程自動發送（正式使用）

建立兩個獨立的 OpenClaw cron job：

| Job 名稱 | 頻率 | 發送目標 |
|---------|------|---------|
| `tw-morning-briefing-0830-discord` | 每日 08:30（台北時間，週一至週六）| 你的 Discord |
| `tw-morning-briefing-0830-line` | 每日 08:30（台北時間，週一至週六）| 你的 LINE |

#### 為什麼要分兩個 job？

因為 Discord 和 LINE 是不同的平台。從同一個 Discord 綁定的對話中試圖直接發 LINE 會被平台的跨平台限制擋住，所以必須分開執行、獨立 delivery。

#### 排程命令的本體

```bash
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  -u /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/tw_morning_briefing.py \
  --announcement-limit 8
```

> ⚠️ **特別注意**：這裡必須用 `.venv/bin/python`，而不是系統的 `python3`。原因是系統 Python 缺少我們安裝的 MCP 與資料抓取相關套件，會出現 `ModuleNotFoundError: No module named 'mcp'`。

#### cron  job 的設定方式摘要

```
名稱：tw-morning-briefing-0830-discord
時間：30 8 * * 1-6 （台北時區）
負載：agentTurn，model=gemma-4-26b-it，lightContext=true，timeout=240s
指令：呼叫上述 python 命令並將輸出透過 announce 發到 Discord
```

```
名稱：tw-morning-briefing-0830-line
時間：30 8 * * 1-6  （台北時區）
負載：agentTurn，model=gemma-4-26b-it，lightContext=true，timeout=240s
指令：呼叫上述 python 命令並將輸出透過 announce 發到 LINE
```

---

## 五、正式上線前的驗證清單

在宣稱部署完成之前，請依序執行並確認每行都沒有錯誤輸出：

```bash
# 1. 驗證 FinMind API 資料可正常讀取
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_finmind.py

# 2. 驗證 MCP 協定本身可以正常溝通
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_protocol.py

# 3. 驗證 SSE 端點可以被 OpenClaw 取得到
/home/node/.openclaw/workspace/projects/openclaw-financial-tw/.venv/bin/python \
  /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/verify_mcp_sse.py

# 4. 驗證晨報可以成功發送（手動跑一次，觀察是否出現在 Discord/LINE）
bash /home/node/.openclaw/workspace/projects/openclaw-financial-tw/scripts/send_tw_morning_briefing.sh
```

四個全部沒有紅字或錯誤，才算部署完成，可以放心交給排程自動跑。

---

## 六、安全須知

| 項目 | 說明 |
|------|------|
| **API Key 不外流** | `FINMIND_TOKEN` 和 `FUGLE_API_KEY` 是你個人的金鑰，絕對不要 commit 到 Git 或分享出去 |
| **.env 隔離** | `.env` 檔案不要分享給任何人，也不應被上傳到任何雲端空間 |
| **朋友使用方式** | 給他 `.env.example`，讓他自己去 [FinMind](https://finmindtrade.com/) 申請免費的 API key |
| **個人化設定** | 每個使用者的 Discord ID / LINE ID 都不同，各自設定自己的 `TW_MORNING_DELIVERIES` |

---

## 七、分享給少數朋友的完整流程

如果你想把這套系統分享給幾個朋友，專案預設不附 `.venv`（因為太大），所以朋友必須根據自己的模式重建環境。以下是完整步驟。

### Step 1：準備乾淨的分享包

確保以下檔案有進 Git，且不包含任何 `.env` 或 `token.json`：

```
openclaw-financial-tw/
├── .env.example           ← 包含所有必要變數的範本，無實際金鑰
├── requirements.txt       ← 所有 Python 套件（朋友需要用這個重建 .venv）
├── docker-compose.yml    ← Docker 啟動腳本
├── Dockerfile
├── mcp/
│   └── openclaw-financial-tw.example.json  ← 設定範本
└── scripts/
    ├── run_finmind_sse.sh
    ├── ensure_finmind_sse.sh
    ├── send_tw_morning_briefing.sh
    └── verify_*.py
```

### Step 2：告訴朋友申請自己的 API Key

1. **FinMind**（主要資料來源，終身免費）：
   - 前往 <https://finmindtrade.com/>
   - 註冊後在個人頁面取得 `FINMIND_TOKEN`

2. **Fugle**（即時股價備援，可選）：
   - 前往 <https://developer.fugle.tw/>
   - 申請後取得 `FUGLE_API_KEY`

### Step 3：朋友選擇模式並重建環境

---

#### 選項 A：朋友選擇模式 A（本機直接跑）

```bash
# 1. 進到專案目錄
cd openclaw-financial-tw

# 2. 重建 Python 虛擬環境（用 requirements.txt）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install tqdm   # 安全墊：finmind 有時會漏裝這個相依套件

# 3. 確認關鍵套件都有裝
.venv/bin/pip list | grep -E "tqdm|finmind|mcp|uvicorn"
# 應該出現：tqdm、finmind、mcp、uvicorn 四個
# 若沒出現，個別補裝：.venv/bin/pip install tqdm finmind mcp uvicorn

# 4. 複製並填寫 .env
cp .env.example .env
# 用文字編輯器開啟 .env，填入 FINMIND_TOKEN 及 TW_MORNING_DELIVERIES

# 5. 啟動 MCP SSE 伺服器
bash scripts/run_finmind_sse.sh

# 6. 驗證
.venv/bin/python scripts/verify_mcp_sse.py
```

---

#### 選項 B：朋友選擇模式 B（Docker）

```bash
cd openclaw-financial-tw
cp .env.example .env
# 填入 FINMIND_TOKEN
docker compose up -d --build
# Docker 會自動從 requirements.txt 安裝所有套件，完全不需要手動管環境

# 驗證容器內的套件
docker exec finmind-tw-mcp pip list | grep -E "tqdm|finmind|mcp|uvicorn"
```

### Step 4：設定 OpenClaw MCP 註冊（兩種模式都要）

無論朋友選模式 A 或 B，都需要在 `~/.openclaw/openclaw.json` 加入同一組設定：

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

### Step 5：驗證晨報並設定排程

```bash
# 手動觸發一次，確認出現在 Discord/LINE
bash scripts/send_tw_morning_briefing.sh
```

確認收到簡報後，在 OpenClaw 的 cron 設定裡加入 `tw-morning-briefing-0830` 的兩個 job，每日 08:30 就會自動送到他自己的 Discord 和 LINE。

---

> **為何不直接給 .venv？**
> `.venv` 在 Linux 上通常 300–800 MB，透過 LINE/Discord 傳輸或 email 分享都不實際。更重要的是，各機器的 Python 版本、作業系統可能不同，直接複製過來的 `.venv` 不一定能用，所以從 `requirements.txt` 重建才是最乾淨的做法。

---

## 八、已知限制

1. **LINE 跨平台限制**：在 Discord 會話綁定的 OpenClaw 無法直接實測驗證 LINE 送達，需在 LINE 對應的綁定會話中单独測試。
2. **股市資料 T+1**：台股當日收盤資料通常在收盘后 1~2 小時才更新，晨報顯示的是「最近可用」資料，不是當下即時行情。
3. **美股夜盤資料時間差**：晨報裡的 SPY/QQQ 涨跌幅是前一日收盤資料，會在少數情況下與開盤前的最新報價有小幅差異。
4. **非投資建議**：所有資料僅供參考，本簡報及系統不構成任何投資建議。

---

*本文件最後更新：2026-05-20*