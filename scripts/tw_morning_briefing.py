#!/usr/bin/env python3
"""Generate and optionally deliver the Taiwan morning briefing."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp" / "finmind_server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("finmind_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_data(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the data list from a briefing sub-result, or [] if the source failed."""
    return result.get("data") or []


def _error_label(result: dict[str, Any]) -> str | None:
    """Return a short error label if the sub-result is an error placeholder."""
    return result.get("_error")


def fmt_amount(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    abs_value = abs(value)
    if abs_value >= 100_000_000:
        return f"{value / 100_000_000:.1f} 億"
    if abs_value >= 10_000:
        return f"{value / 10_000:.1f} 萬"
    return f"{value:,.0f}"


def fmt_pct(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def latest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[-1] if rows else {}


def render_briefing(payload: dict[str, Any]) -> str:
    macro = payload.get("macro") or {}
    usd_result = macro.get("usd_ntd") or []
    rates_result = macro.get("policy_rates") or []
    m2_result = macro.get("m2") or []
    cpi_result = macro.get("cpi") or []
    gdp_result = macro.get("gdp") or []

    # macro values are already plain lists (extracted from .data in briefing tool)
    usd = latest(usd_result if isinstance(usd_result, list) else [])
    rates = latest(rates_result if isinstance(rates_result, list) else [])
    m2 = latest(m2_result if isinstance(m2_result, list) else [])
    cpi = latest(cpi_result if isinstance(cpi_result, list) else [])
    gdp = latest(gdp_result if isinstance(gdp_result, list) else [])

    taiex_raw = payload.get("taiex_total_return_index")
    taiex: list[dict[str, Any]] = (
        taiex_raw if isinstance(taiex_raw, list) else
        _safe_data(taiex_raw) if isinstance(taiex_raw, dict) else []
    )
    us_raw = payload.get("us_market_context")
    us_market: list[dict[str, Any]] = (
        us_raw if isinstance(us_raw, list) else
        _safe_data(us_raw) if isinstance(us_raw, dict) else []
    )
    inst_raw = payload.get("institutional_market_summary")
    institutional: list[dict[str, Any]] = (
        inst_raw if isinstance(inst_raw, list) else
        _safe_data(inst_raw) if isinstance(inst_raw, dict) else []
    )
    announcements_raw = payload.get("major_announcements_summary")
    announcements: list[dict[str, Any]] = (
        announcements_raw if isinstance(announcements_raw, list) else []
    )
    events_raw = payload.get("investor_conference_events")
    events: list[dict[str, Any]] = (
        events_raw if isinstance(events_raw, list) else
        _safe_data(events_raw) if isinstance(events_raw, dict) else []
    )

    # collect any failed sources to surface in the footer
    errors: list[str] = []
    for label, raw in [
        ("TAIEX TRI", taiex_raw), ("美股", us_raw), ("法人彙總", inst_raw),
        ("重大訊息", announcements_raw), ("法說會", events_raw),
    ]:
        if isinstance(raw, dict) and raw.get("_error"):
            errors.append(f"{label}: {raw['_error']}")

    lines = [
        "台股晨間簡報",
        f"產生時間 UTC: {payload.get('generated_at_utc')}",
        "",
        "大盤指數",
    ]
    if len(taiex) >= 2:
        prev, cur = taiex[-2], taiex[-1]
        # FinMind TaiwanStockTotalReturnIndex uses "price"; fall back to "close"/"Close"
        cur_price = cur.get("price") or cur.get("close") or cur.get("Close")
        prev_price = prev.get("price") or prev.get("close") or prev.get("Close")
        ret = None
        if cur_price and prev_price:
            ret = (cur_price / prev_price - 1) * 100
        lines.append(f"- TAIEX TRI {cur.get('date')}: {cur_price} ({fmt_pct(ret)})")
    elif taiex:
        cur = taiex[-1]
        cur_price = cur.get("price") or cur.get("close") or cur.get("Close")
        lines.append(f"- TAIEX TRI {cur.get('date')}: {cur_price}")
    else:
        lines.append("- TAIEX TRI: 資料暫時無法取得")

    lines += ["", "前日三大法人"]
    if institutional:
        for row in institutional:
            lines.append(f"- {row.get('name')}: 買超/賣超 {fmt_amount(row.get('net_amount_ntd'))} NTD")
    else:
        lines.append("- 資料暫時無法取得")

    lines += ["", "美股夜盤影響"]
    if us_market:
        for row in us_market:
            lines.append(f"- {row.get('symbol')} {row.get('latest_date')}: {fmt_pct(row.get('daily_return_pct'))}")
    else:
        lines.append("- 資料暫時無法取得")

    lines += ["", "總經背景"]
    lines.append(f"- USD/NTD {usd.get('date') or 'n/a'}: {usd.get('usd_ntd') or 'n/a'}")
    lines.append(f"- 重貼現率 {rates.get('date') or 'n/a'}: {rates.get('rediscount_rate_pct') or 'n/a'}%")
    lines.append(f"- M2 {m2.get('period') or 'n/a'}: YoY {fmt_pct(m2.get('yoy_pct'))}")
    lines.append(f"- CPI {cpi.get('period') or 'n/a'}: YoY {fmt_pct(cpi.get('yoy_pct'))}")
    lines.append(f"- GDP {gdp.get('period') or 'n/a'}: real growth {fmt_pct(gdp.get('real_gdp_growth_pct'))}")

    lines += ["", "重大訊息"]
    if announcements:
        for item in announcements[:5]:
            lines.append(f"- {item.get('company_id')} {item.get('company_name')}: {item.get('title')}")
    else:
        lines.append("- 無資料")

    lines += ["", "法說/業績發表"]
    if events:
        for item in events[:5]:
            lines.append(f"- {item.get('tag')}: {item.get('title')}")
    else:
        lines.append("- 無資料")

    if errors:
        lines += ["", "⚠️ 部分資料來源暫時無法取得:"]
        for err in errors:
            lines.append(f"  - {err}")

    lines += ["", "註: 本簡報為資料彙整與研究輔助，不是投資建議。"]
    return "\n".join(lines)


def deliver(message: str, deliveries: list[str]) -> None:
    for delivery in deliveries:
        if ":" not in delivery:
            raise ValueError("--deliver must use channel:target, e.g. discord:user:123 or line:Uxxxx")
        channel, target = delivery.split(":", 1)
        subprocess.run(
            ["openclaw", "message", "send", "--channel", channel, "--target", target, "--message", message],
            check=True,
        )


def deliveries_from_env() -> list[str]:
    raw = os.getenv("TW_MORNING_DELIVERIES", "").strip()
    if not raw:
        return []
    values: list[str] = []
    for part in raw.replace("\n", ",").split(","):
        item = part.strip()
        if item:
            values.append(item)
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--announcement-limit", type=int, default=8)
    parser.add_argument("--deliver", action="append", default=[], help="Delivery as channel:target. Repeat for Discord and LINE.")
    parser.add_argument("--deliver-from-env", action="store_true", help="Append TW_MORNING_DELIVERIES from the environment.")
    parser.add_argument("--send", action="store_true", help="Actually send delivery messages. Default prints only.")
    args = parser.parse_args()

    server = load_server()
    payload = server.get_tw_market_briefing(announcement_limit=args.announcement_limit)
    message = render_briefing(payload)
    print(message)
    deliveries = list(args.deliver)
    if args.deliver_from_env:
        deliveries.extend(deliveries_from_env())
    # Preserve order but avoid duplicate sends to the same channel target.
    deliveries = list(dict.fromkeys(deliveries))
    if args.send:
        if not deliveries:
            raise ValueError("no delivery targets configured; use --deliver or --deliver-from-env with TW_MORNING_DELIVERIES")
        deliver(message, deliveries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
