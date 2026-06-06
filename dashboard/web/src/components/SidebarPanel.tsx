import type { AnalysisResponse, ChartResponse, QuoteResponse } from "../lib/api";

type Props = {
  quote: QuoteResponse | null;
  chart: ChartResponse | null;
  analysis: AnalysisResponse | null;
  mode: "auto" | "manual";
  lastRefreshLabel: string;
};

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return new Intl.NumberFormat("zh-TW").format(value);
}

function renderLevel(label: string, low: number, high: number): string {
  return label + " " + formatNumber(low) + " - " + formatNumber(high);
}

export function SidebarPanel({ quote, chart, analysis, mode, lastRefreshLabel }: Props) {
  const latestCandle = chart && chart.candles.length ? chart.candles[chart.candles.length - 1] : undefined;
  const previousCandle = chart && chart.candles.length > 1 ? chart.candles[chart.candles.length - 2] : undefined;
  const dayRange = latestCandle ? latestCandle.high - latestCandle.low : null;
  const dailySpread = latestCandle?.spread ?? null;
  const volumeDelta = latestCandle && previousCandle ? latestCandle.volume - previousCandle.volume : null;
  const summary = analysis?.technical_summary;
  const levels = analysis?.key_levels;
  const indicators = analysis?.indicator_summary ?? [];

  return (
    <aside className="sidebar">
      <section className="panel sidebar-card">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Phase 0 Output</p>
            <h2>資料契約摘要</h2>
          </div>
        </div>
        <dl className="stats-list">
          <div><dt>更新模式</dt><dd>{mode === "auto" ? "即時自動報價" : "手動更新"}</dd></div>
          <div><dt>最後刷新</dt><dd>{lastRefreshLabel}</dd></div>
          <div><dt>資料來源</dt><dd>{(quote?.meta.source ?? "--") + " / " + (chart?.meta.source ?? "--")}</dd></div>
          <div><dt>快取 TTL</dt><dd>{String(quote?.meta.cache_ttl_seconds ?? "--") + "s / " + String(chart?.meta.cache_ttl_seconds ?? "--") + "s"}</dd></div>
        </dl>
      </section>

      <section className="panel sidebar-card">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Phase 2</p>
            <h2>技術分析總覽</h2>
          </div>
        </div>
        <dl className="stats-list">
          <div><dt>趨勢方向</dt><dd>{summary?.trend_direction ?? "--"}</dd></div>
          <div><dt>均線排列</dt><dd>{summary?.ma_alignment ?? "--"}</dd></div>
          <div><dt>布林位置</dt><dd>{summary?.bb_position ?? "--"}</dd></div>
          <div><dt>布林開口</dt><dd>{summary?.bb_channel ?? "--"}</dd></div>
          <div><dt>量價關係</dt><dd>{summary?.vol_price_relation ?? "--"}</dd></div>
        </dl>
        <p className="muted-copy">{summary?.composite_evaluation ?? "分析資料載入中"}</p>
      </section>

      <section className="panel sidebar-card">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Phase 2</p>
            <h2>關鍵價位</h2>
          </div>
        </div>
        <ul className="roadmap-list">
          <li>{levels ? renderLevel("壓力區", levels.resistance.low, levels.resistance.high) : "壓力區載入中"}</li>
          <li>{levels ? renderLevel("回檔區", levels.pullback.low, levels.pullback.high) : "回檔區載入中"}</li>
          <li>{levels ? renderLevel("支撐區", levels.support.low, levels.support.high) : "支撐區載入中"}</li>
          <li>{"最新收盤 " + formatNumber(latestCandle?.close) + " / 日內振幅 " + formatNumber(dayRange)}</li>
          <li>{"當日價差 " + formatNumber(dailySpread) + " / 量差 " + formatNumber(volumeDelta)}</li>
        </ul>
      </section>

      <section className="panel sidebar-card">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Phase 2</p>
            <h2>目前判讀</h2>
          </div>
        </div>
        <ul className="roadmap-list">
          <li>{indicators[0] ? indicators[0].name + "：" + indicators[0].signal : "KD 計算中"}</li>
          <li>{indicators[1] ? indicators[1].name + "：" + indicators[1].signal : "MACD 計算中"}</li>
          <li>{indicators[3] ? indicators[3].name + "：" + indicators[3].signal : "布林通道計算中"}</li>
          <li>{"刷新模式：" + (mode === "auto" ? "自動輪詢 10 秒報價" : "由使用者手動更新全資料")}</li>
        </ul>
      </section>
    </aside>
  );
}
