import type { MultiPeriodResponse } from "../lib/api";

type Props = {
  data: MultiPeriodResponse | null;
};

function buildPath(values: number[], width: number, height: number): string {
  if (!values.length) {
    return "";
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * height;
      return (index === 0 ? "M" : "L") + x.toFixed(2) + " " + y.toFixed(2);
    })
    .join(" ");
}

export function MultiPeriodPanel({ data }: Props) {
  const periods = data?.periods ?? [];

  return (
    <section className="panel multi-period-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 3</p>
          <h2>多週期縮圖</h2>
        </div>
      </div>
      <div className="multi-period-grid">
        {periods.length ? periods.map((period) => {
          const closes = period.candles.map((item) => item.close);
          const path = buildPath(closes, 220, 70);
          const tone = period.change_pct > 0 ? "text-up" : period.change_pct < 0 ? "text-down" : "text-flat";
          return (
            <article className="mini-chart-card" key={period.id}>
              <div className="mini-chart-head">
                <strong>{period.label}</strong>
                <span className={tone}>{period.change_pct > 0 ? "+" : ""}{period.change_pct.toFixed(2)}%</span>
              </div>
              <svg viewBox="0 0 220 70" className="mini-chart-svg" preserveAspectRatio="none">
                <path d={path} fill="none" stroke="currentColor" strokeWidth="2.25" />
              </svg>
              <div className="mini-chart-meta">
                <span>趨勢 {period.trend}</span>
                <span>收盤 {period.last_close.toFixed(2)}</span>
              </div>
              <p>{period.note}</p>
            </article>
          );
        }) : <p>多週期資料載入中</p>}
      </div>
    </section>
  );
}
