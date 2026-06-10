import type { PatternResponse } from "../lib/api";

type Props = {
  data: PatternResponse | null;
};

function formatValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(2);
}

export function PatternAnalysisPanel({ data }: Props) {
  const patterns = data?.patterns;
  const w = patterns?.w_bottom;
  const m = patterns?.m_top;

  return (
    <section className="panel sidebar-card">
      <div className="panel-header">
        <div>
          <p className="eyebrow">型態</p>
          <h2>型態分析</h2>
        </div>
      </div>
      <div className="pattern-grid">
        <div className="pattern-card">
          <strong>W 底</strong>
          <p>{w?.stage ?? "載入中"}</p>
          <p>左底 {formatValue(w?.l1_price)} / 右底 {formatValue(w?.l2_price)}</p>
          <p>頸線 {formatValue(w?.neckline)}</p>
          <p>{w?.reason ?? "--"}</p>
        </div>
        <div className="pattern-card">
          <strong>M 頭</strong>
          <p>{m?.stage ?? "載入中"}</p>
          <p>左峰 {formatValue(m?.h1_price)} / 右峰 {formatValue(m?.h2_price)}</p>
          <p>頸線 {formatValue(m?.neckline)}</p>
          <p>{m?.reason ?? "--"}</p>
        </div>
      </div>
      <p className="muted-copy">目前主導型態：{patterns?.dominant_pattern ?? "none"}</p>
    </section>
  );
}
