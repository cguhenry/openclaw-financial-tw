import type { QuoteResponse } from "../lib/api";

function formatNumber(value: number | null | undefined, options?: Intl.NumberFormatOptions): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return new Intl.NumberFormat("zh-TW", options).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return prefix + value.toFixed(2) + "%";
}

type Props = {
  data: QuoteResponse | null;
};

export function StockHeader({ data }: Props) {
  const quote = data?.quote;
  const change = quote?.change ?? null;
  const tone = change === null ? "neutral" : change > 0 ? "up" : change < 0 ? "down" : "neutral";
  const className = "header-card tone-" + tone;

  return (
    <section className={className}>
      <div className="header-main">
        <div className="stock-ident">
          <p className="eyebrow">OpenClaw Financial TW</p>
          <h1>
            {data?.stock.name ?? "載入中"} <span>{data?.stock.stock_id ?? "--"}</span>
          </h1>
          <p className="market-meta">
            {(quote?.exchange ?? "--") + " / " + (quote?.market ?? "--") + " / " + (quote?.is_close ? "收盤" : "盤中")}
          </p>
        </div>
        <div className="price-block">
          <div className="price-value">{formatNumber(quote?.price)}</div>
          <div className="price-delta">
            <span>{change === null ? "--" : (change > 0 ? "+" : "") + formatNumber(change)}</span>
            <span>{formatPercent(quote?.change_pct)}</span>
          </div>
        </div>
      </div>
      <div className="header-stats">
        <div><label>成交量</label><strong>{formatNumber(quote?.volume)}</strong></div>
        <div><label>成交值</label><strong>{formatNumber(quote?.trade_value)}</strong></div>
        <div><label>買 / 賣</label><strong>{formatNumber(quote?.bid) + " / " + formatNumber(quote?.ask)}</strong></div>
        <div><label>日高 / 日低</label><strong>{formatNumber(quote?.high) + " / " + formatNumber(quote?.low)}</strong></div>
      </div>
    </section>
  );
}
