#!/usr/bin/env python3
"""Direct smoke test for the FinMind MCP tool functions."""

from __future__ import annotations

import importlib.util
from pathlib import Path


SERVER_PATH = Path(__file__).resolve().parents[1] / "mcp" / "finmind_server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("finmind_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    server = load_server()
    checks = [
        ("price", lambda: server.get_stock_price_daily("2330", "2026-05-01", max_rows=3)),
        ("income", lambda: server.get_income_statement("2330", "2025-01-01", max_rows=3)),
        ("revenue", lambda: server.get_month_revenue("2330", "2026-01-01", max_rows=3)),
        ("institutional", lambda: server.get_institutional_flows("2330", "2026-05-01", max_rows=3)),
        ("dividend", lambda: server.get_dividend_policy("2330", "2020-01-01", max_rows=3)),
        ("shareholding_dist", lambda: server.get_shareholding_dist("2330", "2026-05-01", max_rows=3)),
        ("foreign_holding", lambda: server.get_foreign_holding_pct("2330", "2026-05-01", max_rows=3)),
        ("quote", lambda: server.get_realtime_quote("2330")),
        ("announcements", lambda: server.get_major_announcements(market="all", limit=3, summary_count=2)),
        ("announcements_otc", lambda: server.get_major_announcements(market="otc", limit=2, summary_count=2)),
        ("announcements_detail", lambda: server.get_major_announcements(market="sii", limit=1, include_details=True)),
        ("usd_ntd", lambda: server.get_usd_ntd_rate(max_rows=3)),
        ("interest_rates", lambda: server.get_interest_rates(max_rows=3)),
        ("money_supply", lambda: server.get_money_supply(measure="M2", max_rows=3)),
        ("cpi", lambda: server.get_cpi_data(max_rows=3)),
        ("gdp", lambda: server.get_gdp_data(start_time="2024", end_time="2025-Q4", max_rows=3)),
        ("taiex_tri", lambda: server.get_taiex_total_return_index("2026-05-01", max_rows=3)),
        ("us_market", lambda: server.get_us_market_context()),
        ("institutional_market", lambda: server.get_institutional_market_summary()),
        ("investor_events", lambda: server.get_investor_conference_events(limit=3)),
        ("market_briefing", lambda: server.get_tw_market_briefing(announcement_limit=3)),
    ]
    for name, check in checks:
        result = check()
        if name == "quote":
            print(f"{name}: dataset={result['dataset']} symbol={result['quote'].get('symbol')}", flush=True)
            if result["quote"].get("symbol") != "2330":
                raise RuntimeError("quote returned wrong symbol")
            continue
        if name.startswith("announcements"):
            print(
                f"{name}: source={result['source']} market={result['market']} "
                f"rows={result['row_count']} returned={result['returned_rows']} "
                f"summary={result['summary_count']} dataset={result['dataset']}",
                flush=True,
            )
            if result["returned_rows"] <= 0:
                raise RuntimeError(f"{name} returned no rows")
            if result["summary_count"] <= 0:
                raise RuntimeError(f"{name} returned no summary rows")
            if name == "announcements_otc" and result["market"] != "otc":
                raise RuntimeError("announcements_otc returned wrong market")
            if name == "announcements_detail" and "detail" not in result["data"][0]:
                raise RuntimeError("announcements_detail returned no detail payload")
            continue
        if name in {"usd_ntd", "interest_rates", "money_supply", "cpi", "gdp", "taiex_tri", "us_market", "institutional_market"}:
            print(f"{name}: source={result['source']} rows={result['row_count']} returned={result['returned_rows']} dataset={result['dataset']}", flush=True)
            if result["returned_rows"] <= 0:
                raise RuntimeError(f"{name} returned no rows")
            continue
        if name == "investor_events":
            print(f"{name}: source={result['source']} rows={result['row_count']} returned={result['returned_rows']} dataset={result['dataset']}", flush=True)
            continue
        if name == "market_briefing":
            print(f"{name}: generated_at={result['generated_at_utc']} macro_keys={sorted(result['macro'])}", flush=True)
            if "macro" not in result or "taiex_total_return_index" not in result:
                raise RuntimeError("market_briefing returned incomplete payload")
            continue
        print(f"{name}: rows={result['row_count']} returned={result['returned_rows']} dataset={result['dataset']}", flush=True)
        if result["row_count"] <= 0:
            raise RuntimeError(f"{name} returned no rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
