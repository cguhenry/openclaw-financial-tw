export type QuoteResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  quote: {
    price: number | null;
    change: number | null;
    change_pct: number | null;
    volume: number | null;
    trade_value: number | null;
    previous_close: number | null;
    open: number | null;
    high: number | null;
    low: number | null;
    bid: number | null;
    ask: number | null;
    market: string | null;
    exchange: string | null;
    is_close: boolean | null;
    last_updated: number | null;
    date: string | null;
  };
  meta: {
    source: string;
    fetched_at: string;
    cache_ttl_seconds: number;
  };
};

export type ChartCandle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnover: number;
  spread: number;
};

export type ChartResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  timeframe: string;
  candles: ChartCandle[];
  meta: {
    source: string;
    dataset: string;
    returned_rows: number;
    fetched_at: string;
    cache_ttl_seconds: number;
  };
};

export type AnalysisResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  technical_summary: {
    trend_direction: string;
    price_position: string;
    ma_alignment: string;
    vol_price_relation: string;
    bb_position: string;
    bb_channel: string;
    composite_evaluation: string;
  };
  key_levels: {
    resistance: { low: number; high: number };
    pullback: { low: number; high: number };
    support: { low: number; high: number };
  };
  indicator_summary: Array<{
    name: string;
    values: string;
    direction: string;
    signal: string;
  }>;
  raw_indicators: {
    kd: { k: number; d: number };
    macd: { dif: number; signal: number; hist: number };
    bollinger: { upper: number; mid: number; lower: number; pct: number };
  };
  meta: {
    source: string;
    generated_at: string;
    cache_ttl_seconds: number;
  };
};

function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured && configured.trim()) {
    return configured.replace(/\/$/, "");
  }
  return "";
}

const API_BASE_URL = resolveApiBaseUrl();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API_BASE_URL + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error((payload && payload.detail) || ("Request failed: " + response.status));
  }
  return response.json() as Promise<T>;
}

export function fetchQuote(stockId: string, forceRefresh = false): Promise<QuoteResponse> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<QuoteResponse>("/api/stocks/" + stockId + "/quote" + suffix);
}

export function fetchChart(stockId: string, forceRefresh = false): Promise<ChartResponse> {
  const query = new URLSearchParams({ timeframe: "daily", limit: "120" });
  if (forceRefresh) {
    query.set("force_refresh", "true");
  }
  return request<ChartResponse>("/api/stocks/" + stockId + "/chart?" + query.toString());
}

export function fetchAnalysis(stockId: string, forceRefresh = false): Promise<AnalysisResponse> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<AnalysisResponse>("/api/stocks/" + stockId + "/analysis" + suffix);
}

export function refreshStock(stockId: string): Promise<{ quote: QuoteResponse; chart: ChartResponse; analysis: AnalysisResponse }> {
  return request("/api/stocks/" + stockId + "/refresh?limit=120", { method: "POST" });
}
