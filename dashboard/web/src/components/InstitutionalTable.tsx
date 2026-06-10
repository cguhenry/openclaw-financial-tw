import type { InstitutionalResponse } from "../lib/api";

type Props = {
  data: InstitutionalResponse | null;
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

export function InstitutionalTable({ data }: Props) {
  const rows = data?.rows ?? [];
  const summary = data?.summary;

  return (
    <section className="panel table-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">法人</p>
          <h2>三大法人</h2>
        </div>
      </div>
      <div className="mini-summary-strip">
        <span>外資 5 日 {formatSigned(summary?.foreign_5d_net)}</span>
        <span>投信 5 日 {formatSigned(summary?.trust_5d_net)}</span>
        <span>自營 5 日 {formatSigned(summary?.dealer_5d_net)}</span>
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
              <tr><td colSpan={5}>法人資料載入中</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
