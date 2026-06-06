import { useEffect, useMemo, useState } from "react";
import { CandlesPanel } from "./components/CandlesPanel";
import { IndicatorTable } from "./components/IndicatorTable";
import { InstitutionalTable } from "./components/InstitutionalTable";
import { MainForcePanel } from "./components/MainForcePanel";
import { MultiPeriodPanel } from "./components/MultiPeriodPanel";
import { PatternAnalysisPanel } from "./components/PatternAnalysisPanel";
import { PredictionPanel } from "./components/PredictionPanel";
import { SidebarPanel } from "./components/SidebarPanel";
import { StockHeader } from "./components/StockHeader";
import { SuggestionPanel } from "./components/SuggestionPanel";
import {
  fetchAnalysis,
  fetchChart,
  fetchInstitutional,
  fetchMainForce,
  fetchMultiPeriod,
  fetchPatterns,
  fetchQuote,
  fetchSignals,
  refreshStock,
  type AnalysisResponse,
  type ChartResponse,
  type InstitutionalResponse,
  type MainForceResponse,
  type MultiPeriodResponse,
  type PatternResponse,
  type QuoteResponse
  , type SignalResponse
} from "./lib/api";

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
  const [institutional, setInstitutional] = useState<InstitutionalResponse | null>(null);
  const [mainForce, setMainForce] = useState<MainForceResponse | null>(null);
  const [multiPeriod, setMultiPeriod] = useState<MultiPeriodResponse | null>(null);
  const [patterns, setPatterns] = useState<PatternResponse | null>(null);
  const [signals, setSignals] = useState<SignalResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);

  async function loadInitialPayload(forceRefresh = false) {
    setIsLoading(true);
    setError(null);
    try {
      const result = await Promise.all([
        fetchQuote(stockId, forceRefresh),
        fetchChart(stockId, forceRefresh),
        fetchAnalysis(stockId, forceRefresh),
        fetchInstitutional(stockId, forceRefresh),
        fetchMainForce(stockId, forceRefresh),
        fetchMultiPeriod(stockId, forceRefresh),
        fetchPatterns(stockId, forceRefresh),
        fetchSignals(stockId, forceRefresh)
      ]);
      setQuote(result[0]);
      setChart(result[1]);
      setAnalysis(result[2]);
      setInstitutional(result[3]);
      setMainForce(result[4]);
      setMultiPeriod(result[5]);
      setPatterns(result[6]);
      setSignals(result[7]);
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
      setInstitutional(payload.institutional);
      setMainForce(payload.main_force);
      setMultiPeriod(payload.multi_period);
      setPatterns(payload.patterns);
      setSignals(payload.signals);
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
          <InstitutionalTable data={institutional} />
          <MainForcePanel data={mainForce} />
        </section>

        <section className="bottom-grid bottom-grid-secondary">
          <MultiPeriodPanel data={multiPeriod} />
          <PatternAnalysisPanel data={patterns} />
          <PredictionPanel data={signals} />
        </section>

        <section className="bottom-grid bottom-grid-secondary">
          <SuggestionPanel data={signals} />
          <div className="panel mini-panel"><p className="eyebrow">Phase 4</p><h3>AI 骨架說明</h3><p>本版勝率與方向預測屬於 rule-based skeleton，重點是先定好 API 契約、UI 位置與可替換邏輯，之後可無痛替換成真模型。</p></div>
          <div className="panel mini-panel"><p className="eyebrow">Next</p><h3>後續擴充</h3><p>下一步可把分鐘資料、真分點主力模型、以及實際訓練好的分類器接到現有 Phase 4 面板，而不需要重新切版。</p></div>
        </section>
      </main>
    </div>
  );
}
