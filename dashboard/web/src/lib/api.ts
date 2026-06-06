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
    last_close: number;
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

export type PatternResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  patterns: {
    dominant_pattern: string;
    w_bottom: {
      formed: boolean;
      stage: string;
      l1_price: number | null;
      l2_price: number | null;
      neckline: number | null;
      breakout: boolean;
      reason: string;
    };
    m_top: {
      formed: boolean;
      stage: string;
      h1_price: number | null;
      h2_price: number | null;
      neckline: number | null;
      breakdown: boolean;
      reason: string;
    };
  };
  meta: {
    source: string;
    fetched_at: string;
    cache_ttl_seconds: number;
  };
};

export type SignalResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  pattern_analysis: PatternResponse["patterns"];
  trading_suggestion: {
    strategy: string;
    breakout_condition: string;
    pullback_plan: string;
    stop_loss: string;
    risk_note: string;
    last_close: number;
  };
  win_rate: {
    value: number;
    label: string;
    basis: string;
    note: string;
    metrics?: {
      win_accuracy: number;
      direction_accuracy: number;
      train_rows: number;
      test_rows: number;
    };
    trained_at?: string;
  };
  direction_prediction: {
    prediction: string;
    prediction_label: string;
    up_pct: number;
    down_pct: number;
    sideways_pct: number;
    confidence: number;
    basis: string;
    note: string;
    metrics?: {
      win_accuracy: number;
      direction_accuracy: number;
      train_rows: number;
      test_rows: number;
    };
    trained_at?: string;
  };
  meta: {
    source: string;
    fetched_at: string;
    cache_ttl_seconds: number;
  };
};

export type InstitutionalResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  rows: Array<{
    date: string;
    foreign: number;
    investment_trust: number;
    dealer_total: number;
    dealer_self: number;
    dealer_hedging: number;
    foreign_dealer_self: number;
    total: number;
  }>;
  summary: {
    foreign_5d_net: number;
    trust_5d_net: number;
    dealer_5d_net: number;
    total_5d_net: number;
  };
  meta: {
    source: string;
    dataset: string;
    fetched_at: string;
    cache_ttl_seconds: number;
  };
};

export type MainForceResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  method: string;
  note: string;
  signal: {
    signal: string;
    color: string;
    message: string;
  };
  rows: Array<{
    date: string;
    proxy_net: number;
    cumulative_net: number;
    institutional_total: number;
    foreign: number;
    investment_trust: number;
    dealer_total: number;
  }>;
  summary: {
    recent_5d_net: number;
    recent_10d_net: number;
    foreign_holding_ratio: number | null;
    foreign_holding_change: number | null;
  };
  meta: {
    source: string;
    fetched_at: string;
    cache_ttl_seconds: number;
  };
};

export type MultiPeriodResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  periods: Array<{
    id: string;
    label: string;
    candles: ChartCandle[];
    trend: string;
    change_pct: number;
    last_close: number;
    note: string | null;
  }>;
  meta: {
    source: string;
    fetched_at: string;
    cache_ttl_seconds: number;
  };
};

export type AlertRecord = {
  id: string;
  stock_id: string;
  side: "buy" | "sell";
  rule_type: "price_at_or_below" | "price_at_or_above" | "breakout" | "breakdown" | "range_entry";
  target_price: number;
  upper_price: number | null;
  cooldown_minutes: number;
  source: "user" | "ai-assisted";
  note: string | null;
  enabled: boolean;
  delivery_channels: string[];
  delivery_targets: string[];
  created_at: string;
  updated_at: string;
  last_triggered_at: string | null;
  last_trigger_price: number | null;
  trigger_count: number;
};

export type AlertEvent = {
  id: string;
  alert_id: string;
  stock_id: string;
  stock_name: string;
  triggered_at: string;
  price: number;
  message: string;
  rule_type: string;
  side: string;
  status: string;
  delivery_results: Array<Record<string, unknown>>;
};

export type AlertCenterResponse = {
  stock: { stock_id: string };
  alerts: AlertRecord[];
  recent_events: AlertEvent[];
  summary: {
    enabled_count: number;
    triggered_24h: number;
    imported_target_count: number;
    background_polling: boolean;
    poll_interval_seconds: number;
  };
  imported_targets: string[];
  meta: {
    generated_at: string;
    state_path: string;
  };
};

export type AlertSuggestion = {
  template_id: string;
  label: string;
  side: "buy" | "sell";
  rule_type: AlertRecord["rule_type"];
  target_price: number;
  upper_price: number | null;
  cooldown_minutes: number;
  source: "ai-assisted";
  note: string;
  delivery_channels: string[];
  delivery_targets: string[];
};

export type AiAlertPreviewResponse = {
  stock: {
    stock_id: string;
    name: string;
  };
  predicted_direction: string;
  predicted_label: string;
  confidence: number;
  suggestions: AlertSuggestion[];
  meta: {
    generated_at: string;
  };
};

export type NotificationTargetsResponse = {
  targets: string[];
  meta: {
    generated_at: string;
    source_count: number;
  };
};

export type AlertUpsertPayload = {
  side: AlertRecord["side"];
  rule_type: AlertRecord["rule_type"];
  target_price: number;
  upper_price?: number | null;
  cooldown_minutes: number;
  source: AlertRecord["source"];
  note?: string | null;
  enabled: boolean;
  delivery_channels: string[];
  delivery_targets: string[];
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

export function fetchInstitutional(stockId: string, forceRefresh = false): Promise<InstitutionalResponse> {
  const query = new URLSearchParams({ days: "10" });
  if (forceRefresh) {
    query.set("force_refresh", "true");
  }
  return request<InstitutionalResponse>("/api/stocks/" + stockId + "/institutional?" + query.toString());
}

export function fetchMainForce(stockId: string, forceRefresh = false): Promise<MainForceResponse> {
  const query = new URLSearchParams({ days: "10" });
  if (forceRefresh) {
    query.set("force_refresh", "true");
  }
  return request<MainForceResponse>("/api/stocks/" + stockId + "/main-force?" + query.toString());
}

export function fetchMultiPeriod(stockId: string, forceRefresh = false): Promise<MultiPeriodResponse> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<MultiPeriodResponse>("/api/stocks/" + stockId + "/multi-period" + suffix);
}

export function fetchPatterns(stockId: string, forceRefresh = false): Promise<PatternResponse> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<PatternResponse>("/api/stocks/" + stockId + "/patterns" + suffix);
}

export function fetchSignals(stockId: string, forceRefresh = false): Promise<SignalResponse> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<SignalResponse>("/api/stocks/" + stockId + "/signals" + suffix);
}

export function trainModels(stockId: string): Promise<{
  stock_id: string;
  trained_at: string;
  metrics: {
    win_accuracy: number;
    direction_accuracy: number;
    train_rows: number;
    test_rows: number;
  };
  model_path: string;
}> {
  return request("/api/stocks/" + stockId + "/train-models", { method: "POST" });
}

export function refreshStock(stockId: string): Promise<{
  quote: QuoteResponse;
  chart: ChartResponse;
  analysis: AnalysisResponse;
  institutional: InstitutionalResponse;
  main_force: MainForceResponse;
  multi_period: MultiPeriodResponse;
  patterns: PatternResponse;
  signals: SignalResponse;
}> {
  return request("/api/stocks/" + stockId + "/refresh?limit=120", { method: "POST" });
}

export function fetchAlerts(stockId: string): Promise<AlertCenterResponse> {
  return request("/api/stocks/" + stockId + "/alerts");
}

export function fetchAiAlertPreview(stockId: string): Promise<AiAlertPreviewResponse> {
  return request("/api/stocks/" + stockId + "/ai-alert-preview");
}

export function createAlert(stockId: string, payload: AlertUpsertPayload): Promise<{ alert: AlertRecord; status: string }> {
  return request("/api/stocks/" + stockId + "/alerts", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAlert(stockId: string, alertId: string, payload: AlertUpsertPayload): Promise<{ alert: AlertRecord; status: string }> {
  return request("/api/stocks/" + stockId + "/alerts/" + alertId, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function testAlert(stockId: string, alertId?: string, forceDelivery = false): Promise<{ events: AlertEvent[]; count: number; generated_at: string }> {
  return request("/api/stocks/" + stockId + "/alerts/test", {
    method: "POST",
    body: JSON.stringify({ alert_id: alertId ?? null, force_delivery: forceDelivery })
  });
}

export function importNotificationTargets(): Promise<NotificationTargetsResponse> {
  return request("/api/stocks/notification-targets/import");
}
