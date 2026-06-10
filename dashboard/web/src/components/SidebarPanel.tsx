import type { AnalysisResponse, ChartResponse, SignalResponse } from "../lib/api";

type Props = {
  chart: ChartResponse | null;
  analysis: AnalysisResponse | null;
  mode: "auto" | "manual";
  signals: SignalResponse | null;
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

export function SidebarPanel({ chart, analysis, mode, signals }: Props) {
  const latestCandle = chart && chart.candles.length ? chart.candles[chart.candles.length - 1] : undefined;
  const previousCandle = chart && chart.candles.length > 1 ? chart.candles[chart.candles.length - 2] : undefined;
  const dayRange = latestCandle ? latestCandle.high - latestCandle.low : null;
  const dailySpread = latestCandle?.spread ?? null;
  const volumeDelta = latestCandle && previousCandle ? latestCandle.volume - previousCandle.volume : null;
  const summary = analysis?.technical_summary;
  const levels = analysis?.key_levels;
  const indicators = analysis?.indicator_summary ?? [];
  const prediction = signals?.direction_prediction;
  const suggestion = signals?.trading_suggestion;
  const winRate = signals?.win_rate;

  return (
    <aside className="sidebar">
      <section className="panel sidebar-card">
        <div className="panel-header">
          <div>
            <p className="eyebrow">決策摘要</p>
            <h2>交易總覽</h2>
          </div>
        </div>
        <dl className="stats-list">
          <div><dt>更新模式</dt><dd>{mode === "auto" ? "即時自動報價" : "手動更新"}</dd></div>
          <div><dt>趨勢方向</dt><dd>{summary?.trend_direction ?? "--"}</dd></div>
          <div><dt>均線排列</dt><dd>{summary?.ma_alignment ?? "--"}</dd></div>
          <div><dt>方向預測</dt><dd>{prediction?.prediction_label ?? "--"}</dd></div>
          <div><dt>預測信心</dt><dd>{prediction?.confidence != null ? prediction.confidence.toFixed(1) + "%" : "--"}</dd></div>
          <div><dt>短線勝率</dt><dd>{winRate?.value != null ? winRate.value.toFixed(1) + "%" : "--"}</dd></div>
          <div><dt>建議策略</dt><dd>{suggestion?.strategy ?? "--"}</dd></div>
        </dl>
        <p className="muted-copy">{summary?.composite_evaluation ?? "分析資料載入中"}</p>
      </section>

      <section className="panel sidebar-card">
        <div className="panel-header">
          <div>
            <p className="eyebrow">交易計畫</p>
            <h2>關鍵價位與條件</h2>
          </div>
        </div>
        <ul className="roadmap-list">
          <li>{levels ? renderLevel("壓力區", levels.resistance.low, levels.resistance.high) : "壓力區載入中"}</li>
          <li>{levels ? renderLevel("回檔區", levels.pullback.low, levels.pullback.high) : "回檔區載入中"}</li>
          <li>{levels ? renderLevel("支撐區", levels.support.low, levels.support.high) : "支撐區載入中"}</li>
          <li>{"突破條件 " + (suggestion?.breakout_condition ?? "--")}</li>
          <li>{"回檔計畫 " + (suggestion?.pullback_plan ?? "--")}</li>
          <li>{"停損條件 " + (suggestion?.stop_loss ?? "--")}</li>
          <li>{"最新收盤 " + formatNumber(latestCandle?.close) + " / 日內振幅 " + formatNumber(dayRange)}</li>
          <li>{"當日價差 " + formatNumber(dailySpread) + " / 量差 " + formatNumber(volumeDelta)}</li>
        </ul>
      </section>

      <section className="panel sidebar-card">
        <div className="panel-header">
          <div>
            <p className="eyebrow">即時判讀</p>
            <h2>技術面觀察</h2>
          </div>
        </div>
        <ul className="roadmap-list">
          <li>{indicators[0] ? indicators[0].name + "：" + indicators[0].signal : "KD 計算中"}</li>
          <li>{indicators[1] ? indicators[1].name + "：" + indicators[1].signal : "MACD 計算中"}</li>
          <li>{indicators[3] ? indicators[3].name + "：" + indicators[3].signal : "布林通道計算中"}</li>
          <li>{"量價關係：" + (summary?.vol_price_relation ?? "--")}</li>
          <li>{"風險提醒：" + (suggestion?.risk_note ?? "--")}</li>
          <li>{"刷新模式：" + (mode === "auto" ? "自動輪詢 10 秒報價" : "由使用者手動更新全資料")}</li>
        </ul>
      </section>
    </aside>
  );
}
