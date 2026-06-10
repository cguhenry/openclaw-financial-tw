import type { InstitutionalResponse, MainForceResponse } from "../lib/api";

type Props = {
  institutional: InstitutionalResponse | null;
  mainForce: MainForceResponse | null;
};

function formatSigned(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return prefix + new Intl.NumberFormat("zh-TW").format(value);
}

function toneClass(value: number): string {
  if (value > 0) {
    return "text-up";
  }
  if (value < 0) {
    return "text-down";
  }
  return "text-flat";
}

function signalClass(color: string | undefined): string {
  if (color === "green") {
    return "signal-green";
  }
  if (color === "red") {
    return "signal-red";
  }
  return "signal-yellow";
}

export function ChipFlowPanel({ institutional, mainForce }: Props) {
  const summary = institutional?.summary;
  const rows = institutional?.rows ?? [];
  const latest = mainForce?.rows?.[mainForce.rows.length - 1];

  return (
    <section className="panel table-panel chip-flow-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">籌碼動向</p>
          <h2>法人 / 主力資金</h2>
        </div>
      </div>

      <div className="mini-summary-strip">
        <span>外資 5 日 {formatSigned(summary?.foreign_5d_net)}</span>
        <span>投信 5 日 {formatSigned(summary?.trust_5d_net)}</span>
        <span>自營 5 日 {formatSigned(summary?.dealer_5d_net)}</span>
        <span>主力 5 日 {formatSigned(mainForce?.summary.recent_5d_net)}</span>
      </div>

      <div className="chip-flow-signal">
        <span className={"signal-dot " + signalClass(mainForce?.signal.color)} />
        <div>
          <strong>{mainForce?.signal.signal ?? "判讀中"}</strong>
          <p className="muted-copy">{mainForce?.signal.message ?? "主力資金方向計算中"}</p>
        </div>
      </div>

      <div className="chip-flow-stats">
        <div><dt>近 10 日主力淨額</dt><dd>{formatSigned(mainForce?.summary.recent_10d_net)}</dd></div>
        <div><dt>外資持股比</dt><dd>{mainForce?.summary.foreign_holding_ratio != null ? mainForce.summary.foreign_holding_ratio.toFixed(2) + "%" : "--"}</dd></div>
        <div><dt>外資持股變化</dt><dd>{mainForce?.summary.foreign_holding_change != null ? formatSigned(mainForce.summary.foreign_holding_change) + " pct" : "--"}</dd></div>
        <div><dt>最新 proxy 淨額</dt><dd>{formatSigned(latest?.proxy_net)}</dd></div>
      </div>

      <div className="indicator-table-wrap">
        <table className="indicator-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>外資</th>
              <th>投信</th>
              <th>自營</th>
              <th>合計</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr key={row.date}>
                <td>{row.date}</td>
                <td className={toneClass(row.foreign)}>{formatSigned(row.foreign)}</td>
                <td className={toneClass(row.investment_trust)}>{formatSigned(row.investment_trust)}</td>
                <td className={toneClass(row.dealer_total)}>{formatSigned(row.dealer_total)}</td>
                <td className={toneClass(row.total)}>{formatSigned(row.total)}</td>
              </tr>
            )) : (
              <tr><td colSpan={5}>籌碼資料載入中</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="muted-copy">方法：{mainForce?.method ?? "--"}</p>
      <p className="muted-copy">{mainForce?.note ?? "主力 proxy 說明載入中"}</p>
    </section>
  );
}
