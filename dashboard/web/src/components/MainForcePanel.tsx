import type { MainForceResponse } from "../lib/api";

type Props = {
  data: MainForceResponse | null;
};

function formatSigned(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return prefix + new Intl.NumberFormat("zh-TW").format(value);
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

export function MainForcePanel({ data }: Props) {
  const latest = data?.rows?.[data.rows.length - 1];

  return (
    <section className="panel sidebar-card">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 3</p>
          <h2>主力進出</h2>
        </div>
      </div>
      <div className="main-force-signal">
        <span className={"signal-dot " + signalClass(data?.signal.color)} />
        <div>
          <strong>{data?.signal.signal ?? "判讀中"}</strong>
          <p className="muted-copy">{data?.signal.message ?? "主力資金方向計算中"}</p>
        </div>
      </div>
      <dl className="stats-list">
        <div><dt>近 5 日淨額</dt><dd>{formatSigned(data?.summary.recent_5d_net)}</dd></div>
        <div><dt>近 10 日淨額</dt><dd>{formatSigned(data?.summary.recent_10d_net)}</dd></div>
        <div><dt>外資持股比</dt><dd>{data?.summary.foreign_holding_ratio != null ? data.summary.foreign_holding_ratio.toFixed(2) + "%" : "--"}</dd></div>
        <div><dt>外資持股變化</dt><dd>{data?.summary.foreign_holding_change != null ? formatSigned(data.summary.foreign_holding_change) + " pct" : "--"}</dd></div>
        <div><dt>最新 proxy 淨額</dt><dd>{formatSigned(latest?.proxy_net)}</dd></div>
        <div><dt>累計 proxy 淨額</dt><dd>{formatSigned(latest?.cumulative_net)}</dd></div>
      </dl>
      <p className="muted-copy">{data?.note ?? "主力 proxy 說明載入中"}</p>
      <p className="muted-copy">方法：{data?.method ?? "--"}</p>
    </section>
  );
}
