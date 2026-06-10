import type { SignalResponse } from "../lib/api";

type Props = {
  data: SignalResponse | null;
};

export function SuggestionPanel({ data }: Props) {
  const suggestion = data?.trading_suggestion;

  return (
    <section className="panel suggestion-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">建議</p>
          <h2>操作建議</h2>
        </div>
      </div>
      <ul className="roadmap-list">
        <li>策略：{suggestion?.strategy ?? "載入中"}</li>
        <li>突破條件：{suggestion?.breakout_condition ?? "--"}</li>
        <li>回檔計畫：{suggestion?.pullback_plan ?? "--"}</li>
        <li>停損條件：{suggestion?.stop_loss ?? "--"}</li>
        <li>風險提醒：{suggestion?.risk_note ?? "--"}</li>
      </ul>
    </section>
  );
}
