import type { AnalysisResponse } from "../lib/api";

type Props = {
  analysis: AnalysisResponse | null;
};

function directionTone(direction: string): string {
  if (direction === "↑") {
    return "up";
  }
  if (direction === "↓") {
    return "down";
  }
  return "flat";
}

export function IndicatorTable({ analysis }: Props) {
  const indicators = analysis?.indicator_summary ?? [];

  return (
    <section className="panel table-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 2</p>
          <h2>技術指標總覽表</h2>
        </div>
      </div>
      <div className="indicator-table-wrap">
        <table className="indicator-table">
          <thead>
            <tr>
              <th>指標</th>
              <th>數值</th>
              <th>方向</th>
              <th>訊號</th>
            </tr>
          </thead>
          <tbody>
            {indicators.length ? indicators.map((item) => (
              <tr key={item.name}>
                <td>{item.name}</td>
                <td>{item.values}</td>
                <td><span className={"direction-pill " + directionTone(item.direction)}>{item.direction}</span></td>
                <td>{item.signal}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={4}>指標計算中</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
