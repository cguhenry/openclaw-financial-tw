import { useEffect, useMemo, useRef, useState } from "react";
import {
  type AnalysisResponse,
  type SignalResponse,
  createAlert,
  fetchAiAlertPreview,
  fetchAlerts,
  importNotificationTargets,
  testAlert,
  updateAlert,
  type AiAlertPreviewResponse,
  type AlertCenterResponse,
  type AlertRecord,
  type AlertSuggestion,
  type QuoteResponse
} from "../lib/api";

type Props = {
  stockId: string;
  quote: QuoteResponse | null;
  analysis: AnalysisResponse | null;
  signals: SignalResponse | null;
};

type FormState = {
  side: "buy" | "sell";
  rule_type: AlertRecord["rule_type"];
  target_price: string;
  upper_price: string;
  cooldown_minutes: string;
  note: string;
  delivery_channels: string;
  delivery_targets: string;
};

const EMPTY_FORM: FormState = {
  side: "buy",
  rule_type: "price_at_or_below",
  target_price: "",
  upper_price: "",
  cooldown_minutes: "120",
  note: "",
  delivery_channels: "discord,line",
  delivery_targets: ""
};

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toPayload(form: FormState) {
  return {
    side: form.side,
    rule_type: form.rule_type,
    target_price: Number(form.target_price),
    upper_price: form.upper_price ? Number(form.upper_price) : null,
    cooldown_minutes: Number(form.cooldown_minutes || "120"),
    source: "user" as const,
    note: form.note.trim() || null,
    enabled: true,
    delivery_channels: splitList(form.delivery_channels.toLowerCase()),
    delivery_targets: splitList(form.delivery_targets)
  };
}

function toUpsertPayload(alert: AlertRecord) {
  return {
    side: alert.side,
    rule_type: alert.rule_type,
    target_price: alert.target_price,
    upper_price: alert.upper_price,
    cooldown_minutes: alert.cooldown_minutes,
    source: alert.source,
    note: alert.note,
    enabled: alert.enabled,
    delivery_channels: alert.delivery_channels,
    delivery_targets: alert.delivery_targets
  };
}

function buildLocalPreview(stockId: string, analysis: AnalysisResponse | null, signals: SignalResponse | null): AiAlertPreviewResponse | null {
  if (!analysis || !signals) {
    return null;
  }
  const levels = analysis.key_levels;
  const suggestion = signals.trading_suggestion;
  return {
    stock: {
      stock_id: stockId,
      name: analysis.stock.name
    },
    predicted_direction: signals.direction_prediction.prediction,
    predicted_label: signals.direction_prediction.prediction_label,
    confidence: signals.direction_prediction.confidence,
    suggestions: [
      {
        template_id: "buy_pullback",
        label: "AI 建議買點: 回檔承接",
        side: "buy",
        rule_type: "price_at_or_below",
        target_price: levels.pullback.high,
        upper_price: null,
        cooldown_minutes: 240,
        source: "ai-assisted",
        note: "價格回檔到建議承接區時提醒，適合偏保守的拉回承接。 " + suggestion.pullback_plan,
        delivery_channels: ["discord", "line"],
        delivery_targets: []
      },
      {
        template_id: "buy_breakout",
        label: "AI 建議買點: 突破追蹤",
        side: "buy",
        rule_type: "breakout",
        target_price: levels.resistance.high,
        upper_price: null,
        cooldown_minutes: 180,
        source: "ai-assisted",
        note: "價格有效突破壓力區上緣時提醒，適合追蹤趨勢延伸。 " + suggestion.breakout_condition,
        delivery_channels: ["discord", "line"],
        delivery_targets: []
      },
      {
        template_id: "sell_resistance",
        label: "AI 建議賣點: 壓力區提醒",
        side: "sell",
        rule_type: "price_at_or_above",
        target_price: levels.resistance.low,
        upper_price: null,
        cooldown_minutes: 180,
        source: "ai-assisted",
        note: "價格接近壓力區高位時提醒，可作為分批獲利或減碼參考。 " + suggestion.risk_note,
        delivery_channels: ["discord", "line"],
        delivery_targets: []
      },
      {
        template_id: "sell_breakdown",
        label: "AI 建議賣點: 支撐失守",
        side: "sell",
        rule_type: "breakdown",
        target_price: levels.support.low,
        upper_price: null,
        cooldown_minutes: 180,
        source: "ai-assisted",
        note: "價格跌破支撐區下緣時提醒，用來控風險或停損。 " + suggestion.stop_loss,
        delivery_channels: ["discord", "line"],
        delivery_targets: []
      }
    ],
    meta: {
      generated_at: new Date().toISOString()
    }
  };
}

export function AlertCenter({ stockId, quote, analysis, signals }: Props) {
  const [center, setCenter] = useState<AlertCenterResponse | null>(null);
  const [preview, setPreview] = useState<AiAlertPreviewResponse | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latestEventIdRef = useRef<string | null>(null);
  const localPreview = useMemo(() => buildLocalPreview(stockId, analysis, signals), [analysis, signals, stockId]);

  async function loadCenter() {
    const nextCenter = await fetchAlerts(stockId);
    setCenter(nextCenter);
    if (!localPreview) {
      const nextPreview = await fetchAiAlertPreview(stockId);
      setPreview(nextPreview);
    }
    const newestId = nextCenter.recent_events[0]?.id ?? null;
    if (latestEventIdRef.current && newestId && latestEventIdRef.current !== newestId) {
      setToast(nextCenter.recent_events[0]?.message ?? "新的價格提醒已觸發");
      window.setTimeout(() => setToast(null), 4500);
    }
    latestEventIdRef.current = newestId;
  }

  useEffect(() => {
    setPreview(localPreview);
  }, [localPreview]);

  useEffect(() => {
    setError(null);
    setToast(null);
    latestEventIdRef.current = null;
    void loadCenter().catch((nextError) => {
      setError(nextError instanceof Error ? nextError.message : "提醒中心載入失敗");
    });
  }, [stockId, localPreview]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void fetchAlerts(stockId)
        .then((nextCenter) => {
          setCenter(nextCenter);
          const newestId = nextCenter.recent_events[0]?.id ?? null;
          if (latestEventIdRef.current && newestId && latestEventIdRef.current !== newestId) {
            setToast(nextCenter.recent_events[0]?.message ?? "新的價格提醒已觸發");
            window.setTimeout(() => setToast(null), 4500);
          }
          latestEventIdRef.current = newestId;
        })
        .catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(interval);
  }, [stockId]);

  useEffect(() => {
    if (!quote?.quote.price || form.target_price) {
      return;
    }
    setForm((current) => ({ ...current, target_price: String(quote.quote.price ?? "") }));
  }, [quote?.quote.price, form.target_price]);

  const badgeTone = useMemo(() => {
    if ((center?.summary.triggered_24h ?? 0) > 0) {
      return "badge-hot";
    }
    if ((center?.summary.enabled_count ?? 0) > 0) {
      return "badge-calm";
    }
    return "badge-neutral";
  }, [center?.summary.enabled_count, center?.summary.triggered_24h]);

  async function handleCreateManualAlert(event: React.FormEvent) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      await createAlert(stockId, toPayload(form));
      setForm((current) => ({ ...EMPTY_FORM, delivery_targets: current.delivery_targets }));
      await loadCenter();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "建立提醒失敗");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleAdoptSuggestion(suggestion: AlertSuggestion) {
    setIsSaving(true);
    setError(null);
    try {
      await createAlert(stockId, {
        ...suggestion,
        enabled: true
      });
      await loadCenter();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "匯入 AI 建議失敗");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleAlert(alert: AlertRecord) {
    setIsSaving(true);
    setError(null);
    try {
      await updateAlert(stockId, alert.id, {
        ...toUpsertPayload(alert),
        enabled: !alert.enabled
      });
      await loadCenter();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "更新提醒失敗");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTestAlert(alertId?: string) {
    setIsSaving(true);
    setError(null);
    try {
      const result = await testAlert(stockId, alertId, false);
      setToast(result.events[0]?.message ?? "已送出測試通知");
      await loadCenter();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "測試提醒失敗");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleImportTargets() {
    setIsSaving(true);
    setError(null);
    try {
      const imported = await importNotificationTargets();
      setForm((current) => ({
        ...current,
        delivery_targets: imported.targets.join(",")
      }));
      setToast(imported.targets.length ? "已匯入通知目標" : "目前沒有可匯入的通知目標");
      await loadCenter();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "匯入通知目標失敗");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="panel alert-center-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">提醒</p>
          <h2>提醒中心</h2>
        </div>
        <div className="panel-meta">
          <span className={badgeTone}>24h 觸發 {center?.summary.triggered_24h ?? 0}</span>
          <span>啟用中 {center?.summary.enabled_count ?? 0}</span>
          <span>輪詢 {center?.summary.poll_interval_seconds ?? "--"}s</span>
        </div>
      </div>

      {toast ? <div className="toast-banner">{toast}</div> : null}
      {error ? <div className="error-banner compact">{error}</div> : null}

      <div className="alert-center-grid">
        <div className="alert-column">
          <h3>手動建立提醒</h3>
          <form className="alert-form" onSubmit={handleCreateManualAlert}>
            <label>
              方向
              <select value={form.side} onChange={(event) => setForm((current) => ({ ...current, side: event.target.value as FormState["side"] }))}>
                <option value="buy">買進</option>
                <option value="sell">賣出</option>
              </select>
            </label>
            <label>
              條件
              <select value={form.rule_type} onChange={(event) => setForm((current) => ({ ...current, rule_type: event.target.value as FormState["rule_type"] }))}>
                <option value="price_at_or_below">跌到目標以下</option>
                <option value="price_at_or_above">漲到目標以上</option>
                <option value="breakout">突破</option>
                <option value="breakdown">跌破</option>
                <option value="range_entry">進入區間</option>
              </select>
            </label>
            <label>
              目標價
              <input value={form.target_price} onChange={(event) => setForm((current) => ({ ...current, target_price: event.target.value }))} placeholder="730" />
            </label>
            <label>
              區間上緣
              <input value={form.upper_price} onChange={(event) => setForm((current) => ({ ...current, upper_price: event.target.value }))} placeholder="僅區間提醒用" />
            </label>
            <label>
              冷卻分鐘
              <input value={form.cooldown_minutes} onChange={(event) => setForm((current) => ({ ...current, cooldown_minutes: event.target.value }))} placeholder="120" />
            </label>
            <label>
              通知通道
              <input value={form.delivery_channels} onChange={(event) => setForm((current) => ({ ...current, delivery_channels: event.target.value }))} placeholder="discord,line" />
            </label>
            <label className="span-2">
              通知目標
              <textarea value={form.delivery_targets} onChange={(event) => setForm((current) => ({ ...current, delivery_targets: event.target.value }))} placeholder="discord:user:123,line:Uxxxx" rows={3} />
            </label>
            <label className="span-2">
              備註
              <textarea value={form.note} onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))} placeholder="例如：盤後只想看手動提醒" rows={2} />
            </label>
            <div className="alert-form-actions span-2">
              <button type="submit" className="secondary-button" disabled={isSaving}>建立提醒</button>
              <button type="button" className="secondary-button" disabled={isSaving} onClick={handleImportTargets}>匯入通知目標</button>
              <button type="button" className="secondary-button" disabled={isSaving} onClick={() => void handleTestAlert()}>測試預設通知</button>
            </div>
          </form>
          <p className="muted-copy">若執行環境沒有 `openclaw` CLI，通知會先留在站內事件與 outbox，不會直接送到外部聊天平台。</p>
          {center?.imported_targets.length ? (
            <div className="pill-row">
              {center.imported_targets.map((target) => (
                <span key={target}>{target}</span>
              ))}
            </div>
          ) : null}
        </div>

        <div className="alert-column">
          <h3>AI 建議價位</h3>
          <p className="muted-copy">
            模型方向：{preview?.predicted_label ?? "--"} / 信心 {preview?.confidence?.toFixed(1) ?? "--"}%
          </p>
          <div className="suggestion-stack">
            {preview?.suggestions.map((suggestion) => (
              <article key={suggestion.template_id} className="alert-card">
                <div>
                  <strong>{suggestion.label}</strong>
                  <p>{suggestion.note}</p>
                </div>
                <div className="panel-meta">
                  <span>{suggestion.rule_type}</span>
                  <span>{suggestion.target_price.toFixed(2)}</span>
                </div>
                <button type="button" className="secondary-button" disabled={isSaving} onClick={() => void handleAdoptSuggestion(suggestion)}>
                  一鍵套用
                </button>
              </article>
            ))}
          </div>
        </div>
      </div>

      <div className="alert-lists">
        <div className="alert-column">
          <h3>已建立提醒</h3>
          <div className="suggestion-stack">
            {center?.alerts.length ? center.alerts.map((alert) => (
              <article key={alert.id} className="alert-card">
                <div>
                  <strong>{alert.side.toUpperCase()} / {alert.rule_type}</strong>
                  <p>目標 {alert.target_price.toFixed(2)} {alert.upper_price ? " - " + alert.upper_price.toFixed(2) : ""}</p>
                  <p>冷卻 {alert.cooldown_minutes} 分鐘 / 來源 {alert.source}</p>
                </div>
                <div className="panel-meta">
                  <span>{alert.enabled ? "已啟用" : "已停用"}</span>
                  <span>觸發 {alert.trigger_count}</span>
                </div>
                <div className="inline-actions">
                  <button type="button" className="secondary-button" disabled={isSaving} onClick={() => void handleToggleAlert(alert)}>
                    {alert.enabled ? "停用" : "啟用"}
                  </button>
                  <button type="button" className="secondary-button" disabled={isSaving} onClick={() => void handleTestAlert(alert.id)}>
                    測試
                  </button>
                </div>
              </article>
            )) : <p className="muted-copy">目前還沒有提醒規則。</p>}
          </div>
        </div>

        <div className="alert-column">
          <h3>最近事件</h3>
          <div className="suggestion-stack">
            {center?.recent_events.length ? center.recent_events.map((event) => (
              <article key={event.id} className="alert-card event-card">
                <strong>{event.status === "test" ? "測試事件" : "提醒觸發"}</strong>
                <p>{event.message}</p>
                <div className="panel-meta">
                  <span>{new Date(event.triggered_at).toLocaleString("zh-TW", { hour12: false })}</span>
                  <span>{event.price.toFixed(2)}</span>
                </div>
              </article>
            )) : <p className="muted-copy">最近尚無事件。</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
