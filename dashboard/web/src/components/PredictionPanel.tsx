import type { SignalResponse } from "../lib/api";

type Props = {
  data: SignalResponse | null;
};

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(value: number): string {
  const start = polarToCartesian(100, 92, 68, 180);
  const end = polarToCartesian(100, 92, 68, 180 + (value / 100) * 180);
  const largeArcFlag = value > 50 ? 1 : 0;
  return ["M", start.x, start.y, "A", 68, 68, 0, largeArcFlag, 1, end.x, end.y].join(" ");
}

export function PredictionPanel({ data }: Props) {
  const winRate = data?.win_rate.value ?? 0;
  const prediction = data?.direction_prediction;

  return (
    <section className="panel prediction-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 4</p>
          <h2>勝率 / 方向預測</h2>
        </div>
      </div>
      <div className="prediction-layout">
        <div className="gauge-wrap">
          <svg viewBox="0 0 200 110" className="gauge-svg">
            <path d="M 32 92 A 68 68 0 0 1 168 92" fill="none" stroke="#2a3344" strokeWidth="16" strokeLinecap="round" />
            <path d={describeArc(winRate)} fill="none" stroke={winRate >= 60 ? "#ef5350" : winRate >= 45 ? "#ffd166" : "#26a69a"} strokeWidth="16" strokeLinecap="round" />
            <text x="100" y="76" textAnchor="middle" className="gauge-value">{winRate.toFixed(1)}%</text>
            <text x="100" y="96" textAnchor="middle" className="gauge-label">{data?.win_rate.label ?? "短線勝率"}</text>
          </svg>
        </div>
        <div className="prediction-bars">
          <div><label>上漲</label><strong>{prediction?.up_pct.toFixed(1) ?? "--"}%</strong></div>
          <div><label>下跌</label><strong>{prediction?.down_pct.toFixed(1) ?? "--"}%</strong></div>
          <div><label>震盪</label><strong>{prediction?.sideways_pct.toFixed(1) ?? "--"}%</strong></div>
          <div><label>結論</label><strong>{prediction?.prediction_label ?? "--"}</strong></div>
          <div><label>信心</label><strong>{prediction?.confidence.toFixed(1) ?? "--"}%</strong></div>
        </div>
      </div>
      <p className="muted-copy">{prediction?.note ?? data?.win_rate.note ?? "AI 預測骨架載入中"}</p>
    </section>
  );
}
