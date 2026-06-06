# Synology NAS 部署指南

本文件說明如何在 Synology NAS 上部署 `openclaw-financial-tw`，包含：

1. MCP SSE server
2. 股票分析儀表板 API
3. 股票分析儀表板 Web

本版本已將 dashboard 對外 web port 設為 **9080**，避免與 NAS 上常見的 8080 服務衝突。

---

## 1. 前提條件

請先確認：

1. NAS 已安裝 **Container Manager**（DSM 7.x）或可用的 Docker 套件
2. NAS 可透過 SSH 登入
3. 你已經有：
   - `FINMIND_TOKEN`
   - `FUGLE_API_KEY`（可選，但建議填）

---

## 2. 專案放置位置

建議把專案放在你習慣管理的共享資料夾，例如：

```bash
/volume1/docker/openclaw-financial-tw
```

如果尚未放上去，可以在 NAS 上：

```bash
cd /volume1/docker
git clone https://github.com/cguhenry/openclaw-financial-tw.git
cd openclaw-financial-tw
```

---

## 3. 建立 `.env`

在專案根目錄建立 `.env`：

```bash
cp .env.example .env
```

至少填這些欄位：

```dotenv
FINMIND_TOKEN=你的_FINMIND_TOKEN
FUGLE_API_KEY=你的_FUGLE_API_KEY

MCP_TRANSPORT=sse
MCP_HOST=0.0.0.0
MCP_PORT=9123

DASHBOARD_API_HOST=0.0.0.0
DASHBOARD_API_PORT=9180
DASHBOARD_CORS_ORIGINS=http://127.0.0.1:9080,http://localhost:9080
```

如果你未來會讓 browser 直接跨 port 打 `9180`，或從其他 hostname / domain 直接呼叫 API，再把對應來源補進 `DASHBOARD_CORS_ORIGINS`。

### 同區網存取時，CORS 要怎麼填

如果你要從同一區網的其他電腦、手機或平板開：

```text
http://192.168.3.33:9080
```

那麼 `.env` 裡的 `DASHBOARD_CORS_ORIGINS` **一定要包含這個來源**，因為瀏覽器會把：

```text
http://192.168.3.33:9080
```

視為實際的 web origin。

建議直接寫成：

```dotenv
DASHBOARD_CORS_ORIGINS=http://127.0.0.1:9080,http://localhost:9080,http://192.168.3.33:9080
```

如果你還會透過其他名稱存取 NAS，例如：

```text
http://nas.local:9080
```

也要一併加入：

```dotenv
DASHBOARD_CORS_ORIGINS=http://127.0.0.1:9080,http://localhost:9080,http://192.168.3.33:9080,http://nas.local:9080
```

修改 `.env` 後，記得重啟 dashboard API：

```bash
docker compose restart stock-dashboard-api
```

若你是第一次部署或有改 image/build 內容，則直接重建：

```bash
docker compose --profile dashboard up -d --build
```

---

## 4. 啟動服務

在專案根目錄執行：

```bash
docker compose --profile dashboard up -d --build
```

這會啟動三個服務：

1. `finmind-tw-mcp`
2. `stock-dashboard-api`
3. `stock-dashboard-web`

---

## 5. Port 對應

目前 compose 預設如下：

| 服務 | 容器內 port | NAS 對外 port |
|------|-------------|---------------|
| MCP SSE | 9123 | 9123 |
| Dashboard API | 9180 | 9180 |
| Dashboard Web | 8080 | 9080 |

所以你實際打開的網址會是：

- Dashboard Web: `http://NAS_IP:9080`
- Dashboard API health: `http://NAS_IP:9180/api/health`
- MCP SSE: `http://NAS_IP:9123/sse`

---

## 6. 驗證

先在 NAS 本機驗證：

```bash
curl http://127.0.0.1:9180/api/health
curl -I http://127.0.0.1:9123/sse
```

再從你的電腦瀏覽器開：

```text
http://你的_NAS_IP:9080
```

---

## 7. 查看狀態與日誌

### 查看容器

```bash
docker compose ps
```

### 看 dashboard API log

```bash
docker compose logs -f stock-dashboard-api
```

### 看 dashboard Web log

```bash
docker compose logs -f stock-dashboard-web
```

### 看 MCP log

```bash
docker compose logs -f finmind-tw-mcp
```

---

## 8. 常用操作

### 重建並重啟

```bash
docker compose --profile dashboard up -d --build
```

### 停止

```bash
docker compose --profile dashboard down
```

### 只重啟 dashboard web

```bash
docker compose restart stock-dashboard-web
```

---

## 9. OpenClaw MCP 設定

如果 OpenClaw 與 NAS 在同一台機器：

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

如果 OpenClaw 在另一台機器，改成 NAS IP：

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

---

## 10. 常見問題

### Q1: 9080 還是撞 port

改 `docker-compose.yml`：

```yaml
  stock-dashboard-web:
    ports:
      - "9090:8080"
```

然後重啟：

```bash
docker compose --profile dashboard up -d --build
```

### Q2: 瀏覽器打得開 Web，但抓不到 API

先檢查：

```bash
curl http://127.0.0.1:9180/api/health
```

如果 API 正常，再檢查 `.env` 的 `DASHBOARD_CORS_ORIGINS` 是否包含你實際開啟 dashboard 的來源。

### Q3: dashboard 畫面空白

先看：

```bash
docker compose logs -f stock-dashboard-web
docker compose logs -f stock-dashboard-api
```

再檢查：

1. `FINMIND_TOKEN` 是否有效
2. `FUGLE_API_KEY` 是否有效
3. NAS 是否能連外到 FinMind / Fugle

---

## 11. 建議

如果你之後要透過網域或反向代理提供 dashboard：

1. 保持容器內 port 不變
2. 只在 Synology Reverse Proxy 那層改外部入口
3. 不要把 compose 裡的內部 service 名稱改掉

這樣後續維護最穩。
