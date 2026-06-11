from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..cache import TTLCache
from ..config import settings
from .market_data import fetch_analysis_payload, fetch_quote_payload, fetch_signal_payload


PREVIEW_CACHE = TTLCache()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


class AlertService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._poller_started = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_path = Path(settings.app_data_dir).resolve() / "dashboard-alerts.json"
        self._outbox_path = Path(settings.app_data_dir).resolve() / "dashboard-notification-outbox.jsonl"
        self._ensure_paths()

    def _ensure_paths(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._outbox_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._state_path.exists():
            self._write_state({"alerts": [], "events": []})

    def _read_state(self) -> dict[str, Any]:
        self._ensure_paths()
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"alerts": [], "events": []}
        payload.setdefault("alerts", [])
        payload.setdefault("events", [])
        return payload

    def _write_state(self, payload: dict[str, Any]) -> None:
        self._state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def start_poller(self) -> None:
        with self._lock:
            if self._poller_started:
                return
            self._poller_started = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._poll_loop, name="dashboard-alert-poller", daemon=True)
            self._thread.start()

    def stop_poller(self) -> None:
        with self._lock:
            if not self._poller_started:
                return
            self._stop_event.set()
            thread = self._thread
            self._thread = None
            self._poller_started = False
        if thread is not None:
            thread.join(timeout=2)

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(max(settings.alert_poll_interval_seconds, 5)):
            try:
                self.evaluate_all_due_alerts()
            except Exception:
                continue

    def _normalize_alert(self, stock_id: str, payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
        upper_price = payload.get("upper_price")
        if upper_price is not None:
            upper_price = round(float(upper_price), 2)
        delivery_channels = sorted({str(item).strip().lower() for item in payload.get("delivery_channels") or [] if str(item).strip()})
        delivery_targets = list(dict.fromkeys(str(item).strip() for item in payload.get("delivery_targets") or [] if str(item).strip()))
        if upper_price is not None and upper_price < float(payload["target_price"]):
            raise ValueError("upper_price must be greater than or equal to target_price")
        created_at = existing["created_at"] if existing else _now_iso()
        return {
            "id": existing["id"] if existing else uuid.uuid4().hex[:12],
            "stock_id": stock_id,
            "side": str(payload["side"]),
            "rule_type": str(payload["rule_type"]),
            "target_price": round(float(payload["target_price"]), 2),
            "upper_price": upper_price,
            "cooldown_minutes": int(payload.get("cooldown_minutes") or settings.alert_default_cooldown_minutes),
            "source": str(payload.get("source") or "user"),
            "note": (payload.get("note") or "").strip() or None,
            "enabled": bool(payload.get("enabled", True)),
            "delivery_channels": delivery_channels,
            "delivery_targets": delivery_targets,
            "created_at": created_at,
            "updated_at": _now_iso(),
            "last_triggered_at": existing.get("last_triggered_at") if existing else None,
            "last_trigger_price": existing.get("last_trigger_price") if existing else None,
            "trigger_count": int(existing.get("trigger_count") or 0) if existing else 0,
        }

    def list_alerts(self, stock_id: str) -> dict[str, Any]:
        state = self._read_state()
        alerts = [item for item in state["alerts"] if item["stock_id"] == stock_id]
        events = [item for item in state["events"] if item["stock_id"] == stock_id]
        events.sort(key=lambda item: item["triggered_at"], reverse=True)
        live_events = [item for item in events if item.get("status") != "test"]
        test_events = [item for item in events if item.get("status") == "test"]
        imported_targets = self.import_notification_targets(peek_only=True)
        recent_24h_cutoff = _now_utc() - timedelta(hours=24)
        triggered_24h = sum(
            1
            for item in live_events
            if datetime.fromisoformat(item["triggered_at"]) >= recent_24h_cutoff
        )
        test_triggered_24h = sum(
            1
            for item in test_events
            if datetime.fromisoformat(item["triggered_at"]) >= recent_24h_cutoff
        )
        return {
            "stock": {"stock_id": stock_id},
            "alerts": sorted(alerts, key=lambda item: item["created_at"], reverse=True),
            "recent_events": live_events[: settings.alert_event_limit],
            "recent_test_events": test_events[: settings.alert_event_limit],
            "summary": {
                "enabled_count": sum(1 for item in alerts if item["enabled"]),
                "triggered_24h": triggered_24h,
                "test_triggered_24h": test_triggered_24h,
                "recent_event_count": len(live_events),
                "recent_test_event_count": len(test_events),
                "imported_target_count": len(imported_targets["targets"]),
                "background_polling": self._poller_started,
                "poll_interval_seconds": settings.alert_poll_interval_seconds,
            },
            "imported_targets": imported_targets["targets"],
            "meta": {
                "generated_at": _now_iso(),
                "state_path": str(self._state_path),
            },
        }

    def create_alert(self, stock_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read_state()
            alert = self._normalize_alert(stock_id, payload)
            state["alerts"].append(alert)
            self._write_state(state)
        return {"alert": alert, "status": "created"}

    def patch_alert(self, stock_id: str, alert_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read_state()
            for index, item in enumerate(state["alerts"]):
                if item["id"] == alert_id and item["stock_id"] == stock_id:
                    next_payload = {**item, **payload}
                    alert = self._normalize_alert(stock_id, next_payload, existing=item)
                    state["alerts"][index] = alert
                    self._write_state(state)
                    return {"alert": alert, "status": "updated"}
        raise ValueError("alert not found")

    def _compose_ai_preview(
        self,
        stock_id: str,
        *,
        analysis: dict[str, Any],
        signals: dict[str, Any],
    ) -> dict[str, Any]:
        levels = analysis["key_levels"]
        suggestion = signals["trading_suggestion"]
        predicted = signals["direction_prediction"]["prediction"]
        notes = {
            "buy_pullback": "價格回檔到建議承接區時提醒，適合偏保守的拉回承接。",
            "buy_breakout": "價格有效突破壓力區上緣時提醒，適合追蹤趨勢延伸。",
            "sell_resistance": "價格接近壓力區高位時提醒，可作為分批獲利或減碼參考。",
            "sell_breakdown": "價格跌破支撐區下緣時提醒，用來控風險或停損。",
        }
        suggestions = [
            {
                "template_id": "buy_pullback",
                "label": "AI 建議買點: 回檔承接",
                "side": "buy",
                "rule_type": "price_at_or_below",
                "target_price": levels["pullback"]["high"],
                "upper_price": None,
                "cooldown_minutes": 240,
                "source": "ai-assisted",
                "note": f"{notes['buy_pullback']} {suggestion['pullback_plan']}",
                "delivery_channels": ["discord", "line"],
                "delivery_targets": [],
            },
            {
                "template_id": "buy_breakout",
                "label": "AI 建議買點: 突破追蹤",
                "side": "buy",
                "rule_type": "breakout",
                "target_price": levels["resistance"]["high"],
                "upper_price": None,
                "cooldown_minutes": 180,
                "source": "ai-assisted",
                "note": f"{notes['buy_breakout']} {suggestion['breakout_condition']}",
                "delivery_channels": ["discord", "line"],
                "delivery_targets": [],
            },
            {
                "template_id": "sell_resistance",
                "label": "AI 建議賣點: 壓力區提醒",
                "side": "sell",
                "rule_type": "price_at_or_above",
                "target_price": levels["resistance"]["low"],
                "upper_price": None,
                "cooldown_minutes": 180,
                "source": "ai-assisted",
                "note": f"{notes['sell_resistance']} {suggestion['risk_note']}",
                "delivery_channels": ["discord", "line"],
                "delivery_targets": [],
            },
            {
                "template_id": "sell_breakdown",
                "label": "AI 建議賣點: 支撐失守",
                "side": "sell",
                "rule_type": "breakdown",
                "target_price": levels["support"]["low"],
                "upper_price": None,
                "cooldown_minutes": 180,
                "source": "ai-assisted",
                "note": f"{notes['sell_breakdown']} {suggestion['stop_loss']}",
                "delivery_channels": ["discord", "line"],
                "delivery_targets": [],
            },
        ]
        return {
            "stock": {"stock_id": stock_id, "name": analysis["stock"]["name"]},
            "predicted_direction": predicted,
            "predicted_label": signals["direction_prediction"]["prediction_label"],
            "confidence": signals["direction_prediction"]["confidence"],
            "suggestions": suggestions,
            "meta": {"generated_at": _now_iso()},
        }

    def build_ai_preview(
        self,
        stock_id: str,
        *,
        force_refresh: bool = False,
        analysis_payload: dict[str, Any] | None = None,
        signal_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cache_key = f"ai-alert-preview:{stock_id}"
        if not force_refresh:
            cached = PREVIEW_CACHE.get(cache_key)
            if cached is not None:
                return cached

        analysis = analysis_payload or fetch_analysis_payload(stock_id, force_refresh=force_refresh)
        signals = signal_payload or fetch_signal_payload(stock_id, force_refresh=force_refresh)
        result = self._compose_ai_preview(stock_id, analysis=analysis, signals=signals)
        return PREVIEW_CACHE.set(cache_key, result, settings.alert_preview_ttl_seconds)

    def import_notification_targets(self, *, peek_only: bool = False) -> dict[str, Any]:
        targets: list[str] = []
        raw_env = []
        deliveries = os.getenv("TW_MORNING_DELIVERIES", "").strip()
        if not deliveries:
            env_path = Path.cwd() / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("TW_MORNING_DELIVERIES="):
                        deliveries = line.split("=", 1)[1].strip()
                        break
        if deliveries:
            raw_env.extend(part.strip() for part in deliveries.replace("\n", ",").split(",") if part.strip())
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            for candidate in (
                payload.get("dashboardDeliveryTargets"),
                ((payload.get("dashboard") or {}).get("deliveryTargets") if isinstance(payload.get("dashboard"), dict) else None),
            ):
                if isinstance(candidate, list):
                    raw_env.extend(str(item).strip() for item in candidate if str(item).strip())
        for item in raw_env:
            if item not in targets:
                targets.append(item)
        result = {"targets": targets, "meta": {"generated_at": _now_iso(), "source_count": len(targets)}}
        if not peek_only:
            return result
        return result

    def _is_due(self, alert: dict[str, Any], current_price: float) -> bool:
        rule_type = alert["rule_type"]
        target_price = float(alert["target_price"])
        if rule_type in {"price_at_or_below", "breakdown"}:
            return current_price <= target_price
        if rule_type in {"price_at_or_above", "breakout"}:
            return current_price >= target_price
        if rule_type == "range_entry":
            upper_price = float(alert["upper_price"] or target_price)
            return target_price <= current_price <= upper_price
        return False

    def _cooldown_active(self, alert: dict[str, Any]) -> bool:
        last_triggered_at = alert.get("last_triggered_at")
        if not last_triggered_at:
            return False
        last = datetime.fromisoformat(last_triggered_at)
        return _now_utc() < last + timedelta(minutes=int(alert["cooldown_minutes"]))

    def _delivery_targets_for_alert(self, alert: dict[str, Any]) -> list[str]:
        explicit = list(dict.fromkeys(item for item in alert.get("delivery_targets") or [] if item))
        if explicit:
            return explicit
        imported = self.import_notification_targets(peek_only=True)["targets"]
        channels = set(alert.get("delivery_channels") or [])
        if not channels:
            return imported
        return [item for item in imported if item.split(":", 1)[0] in channels]

    def _notify_external(self, message: str, alert: dict[str, Any], *, force_delivery: bool = False) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        targets = self._delivery_targets_for_alert(alert)
        if not targets:
            return [{"status": "skipped", "reason": "no_delivery_targets"}]
        if shutil.which("openclaw") is None:
            return [{"status": "queued", "reason": "openclaw_cli_not_found", "target_count": len(targets)}]
        for item in targets:
            if ":" not in item:
                results.append({"target": item, "status": "error", "reason": "invalid_target"})
                continue
            channel, target = item.split(":", 1)
            command = [
                "openclaw",
                "message",
                "send",
                "--channel",
                channel,
                "--target",
                target,
                "--message",
                message,
            ]
            try:
                completed = subprocess.run(command, check=True, timeout=20, capture_output=True, text=True)
                results.append({"target": item, "status": "sent", "stdout": completed.stdout.strip(), "force_delivery": force_delivery})
            except Exception as exc:
                results.append({"target": item, "status": "error", "reason": str(exc)})
        return results

    def _append_outbox(self, event: dict[str, Any]) -> None:
        with self._outbox_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def evaluate_all_due_alerts(self, *, stock_id: str | None = None, force_delivery: bool = False, test_alert: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            state = self._read_state()
            alerts = [item for item in state["alerts"] if item["enabled"]]
            if stock_id:
                alerts = [item for item in alerts if item["stock_id"] == stock_id]
            if test_alert is not None:
                alerts = [test_alert]

            grouped: dict[str, list[dict[str, Any]]] = {}
            for alert in alerts:
                grouped.setdefault(alert["stock_id"], []).append(alert)

            new_events: list[dict[str, Any]] = []
            for current_stock_id, stock_alerts in grouped.items():
                quote_payload = fetch_quote_payload(current_stock_id, force_refresh=True)
                current_price = quote_payload["quote"]["price"]
                if current_price is None:
                    continue
                stock_name = quote_payload["stock"]["name"]
                for alert in stock_alerts:
                    if self._cooldown_active(alert) and test_alert is None:
                        continue
                    if test_alert is None and not self._is_due(alert, float(current_price)):
                        continue
                    message = (
                        f"[{stock_name} {current_stock_id}] "
                        f"{'測試通知' if test_alert is not None else '價格提醒'}: "
                        f"{alert['side']} / {alert['rule_type']} / 目標 {float(alert['target_price']):.2f} / 現價 {float(current_price):.2f}"
                    )
                    delivery_results = self._notify_external(message, alert, force_delivery=force_delivery)
                    event = {
                        "id": uuid.uuid4().hex[:12],
                        "alert_id": alert["id"],
                        "stock_id": current_stock_id,
                        "stock_name": stock_name,
                        "triggered_at": _now_iso(),
                        "price": round(float(current_price), 2),
                        "message": message,
                        "rule_type": alert["rule_type"],
                        "side": alert["side"],
                        "delivery_results": delivery_results,
                        "status": "triggered" if test_alert is None else "test",
                    }
                    new_events.append(event)
                    self._append_outbox(event)
                    if test_alert is None:
                        alert["last_triggered_at"] = event["triggered_at"]
                        alert["last_trigger_price"] = event["price"]
                        alert["trigger_count"] = int(alert.get("trigger_count") or 0) + 1
            if new_events:
                state["events"] = (new_events + state["events"])[:400]
                self._write_state(state)
        return {"events": new_events, "count": len(new_events), "generated_at": _now_iso()}

    def test_alert(self, stock_id: str, alert_id: str | None, *, force_delivery: bool = False) -> dict[str, Any]:
        state = self._read_state()
        alert: dict[str, Any] | None = None
        if alert_id:
            for item in state["alerts"]:
                if item["id"] == alert_id and item["stock_id"] == stock_id:
                    alert = item
                    break
            if alert is None:
                raise ValueError("alert not found")
        else:
            preview = self.build_ai_preview(stock_id)["suggestions"][0]
            alert = self._normalize_alert(stock_id, preview)
        return self.evaluate_all_due_alerts(stock_id=stock_id, force_delivery=force_delivery, test_alert=alert)


alert_service = AlertService()
