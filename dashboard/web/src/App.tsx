import { useEffect, useMemo, useState } from "react";
import { CandlesPanel } from "./components/CandlesPanel";
import { IndicatorTable } from "./components/IndicatorTable";
import { SidebarPanel } from "./components/SidebarPanel";
import { StockHeader } from "./components/StockHeader";
import { fetchAnalysis, fetchChart, fetchQuote, refreshStock, type AnalysisResponse, type ChartResponse, type QuoteResponse } from "./lib/api";

type Mode = "auto" | "manual";

const MODE_STORAGE_KEY = "openclaw-financial-tw:quote-mode";

function readInitialMode(): Mode {
  const saved = window.localStorage.getItem(MODE_STORAGE_KEY);
  return saved === "manual" ? "manual" : "auto";
}

export default function App() {
  const [stockIdInput, setStockIdInput] = useState("2330");
  const [stockId, setStockId] = useState("2330");
  const [mode, setMode] = useState<Mode>(readInitialMode);
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [chart, setChart] = useState<ChartResponse | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);

  async function loadInitialPayload(forceRefresh = false) {
    setIsLoading(true);
    setError(null);
    try {
      const result = await Promise.all([fetchQuote(stockId, forceRefresh), fetchChart(stockId, forceRefresh), fetchAnalysis(stockId, forceRefresh)]);
      setQuote(result[0]);
      setChart(result[1]);
      setAnalysis(result[2]);
      setLastRefreshAt(new Date());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadQuoteOnly() {
    try {
      const nextQuote = await fetchQuote(stockId, true);
      setQuote(nextQuote);
      setLastRefreshAt(new Date());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unknown error");
    }
  }

  useEffect(() => {
    void loadInitialPayload();
  }, [stockId]);

  useEffect(() => {
    window.localStorage.setItem(MODE_STORAGE_KEY, mode);
    if (mode !== "auto") {
      return;
    }
    const interval = window.setInterval(() => {
      void loadQuoteOnly();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [mode, stockId]);

  const lastRefreshLabel = useMemo(() => {
    if (!lastRefreshAt) {
      return "尚未刷新";
    }
    return lastRefreshAt.toLocaleTimeString("zh-TW", { hour12: false });
  }, [lastRefreshAt]);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (stockIdInput.trim()) {
      setStockId(stockIdInput.trim().toUpperCase());
    }
  }

  async function handleRefresh() {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await refreshStock(stockId);
      setQuote(payload.quote);
      setChart(payload.chart);
      setAnalysis(payload.analysis);
      setLastRefreshAt(new Date());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="page-backdrop" />
      <main className="page">
        <div className="toolbar">
          <form className="toolbar-form" onSubmit={handleSubmit}>
            <label>
              股票代號
              <input value={stockIdInput} onChange={(event) => setStockIdInput(event.target.value)} placeholder="2330" />
            </label>
            <button type="submit">載入</button>
          </form>

          <div className="toolbar-controls">
            <div className="mode-toggle" role="group" aria-label="報價模式">
              <button className={mode === "auto" ? "active" : ""} onClick={() => setMode("auto")} type="button">即時自動報價</button>
              <button className={mode === "manual" ? "active" : ""} onClick={() => setMode("manual")} type="button">手動更新</button>
            </div>
            <button type="button" className="secondary-button" onClick={handleRefresh} disabled={isLoading}>
              {isLoading ? "更新中..." : "立即更新"}
            </button>
          </div>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}

        <StockHeader data={quote} />

        <section className="main-grid">
          <CandlesPanel data={chart} analysis={analysis} />
          <SidebarPanel quote={quote} chart={chart} analysis={analysis} mode={mode} lastRefreshLabel={lastRefreshLabel} />
        </section>

        <section className="bottom-grid">
          <IndicatorTable analysis={analysis} />
          <div className="panel mini-panel"><p className="eyebrow">Reserved</p><h3>日 K / 週 K 縮圖</h3><p>先保留版位，避免 Phase 1 把多週期資料做半套。</p></div>
          <div className="panel mini-panel"><p className="eyebrow">Reserved</p><h3>型態分析 / AI</h3><p>延後到資料與指標穩定後再開。</p></div>
        </section>
      </main>
    </div>
  );
}
