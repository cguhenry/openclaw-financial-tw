#!/usr/bin/env python3
"""MCP protocol smoke test for the FinMind server over stdio."""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    server = StdioServerParameters(
        command=str(ROOT / ".venv" / "bin" / "python"),
        args=[str(ROOT / "mcp" / "finmind_server.py")],
        env={"MCP_TRANSPORT": "stdio"},
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            required = {
                "get_stock_price_daily",
                "get_income_statement",
                "get_month_revenue",
                "get_institutional_flows",
                "get_dividend_policy",
                "get_realtime_quote",
                "get_major_announcements",
                "get_foreign_holding_pct",
                "get_usd_ntd_rate",
                "get_interest_rates",
                "get_money_supply",
                "get_cpi_data",
                "get_gdp_data",
                "get_taiex_total_return_index",
                "get_us_market_context",
                "get_institutional_market_summary",
                "get_tw_market_briefing",
                "get_investor_conference_events",
                "get_equity_research_snapshot",
            }
            missing = sorted(required - set(names))
            if missing:
                raise RuntimeError(f"missing tools: {missing}")
            result = await session.call_tool(
                "get_stock_price_daily",
                {"stock_id": "2330", "start_date": "2026-05-01", "max_rows": 2},
            )
            quote = await session.call_tool("get_realtime_quote", {"stock_id": "2330"})
            announcements = await session.call_tool("get_major_announcements", {"limit": 2})
            otc_announcements = await session.call_tool(
                "get_major_announcements",
                {"market": "otc", "limit": 1, "summary_count": 1},
            )
            usd_ntd = await session.call_tool("get_usd_ntd_rate", {"max_rows": 1})
            cpi = await session.call_tool("get_cpi_data", {"max_rows": 1})
            gdp = await session.call_tool("get_gdp_data", {"start_time": "2024", "end_time": "2025-Q4", "max_rows": 1})
            us_market = await session.call_tool("get_us_market_context", {})
            institutional = await session.call_tool("get_institutional_market_summary", {})
            briefing = await session.call_tool("get_tw_market_briefing", {"announcement_limit": 2})
            events = await session.call_tool("get_investor_conference_events", {"limit": 2})
            print(
                f"tools={len(names)} required=ok "
                f"price_blocks={len(result.content)} quote_blocks={len(quote.content)} "
                f"announcement_blocks={len(announcements.content)} "
                f"otc_announcement_blocks={len(otc_announcements.content)} "
                f"usd_ntd_blocks={len(usd_ntd.content)} cpi_blocks={len(cpi.content)} "
                f"gdp_blocks={len(gdp.content)} us_market_blocks={len(us_market.content)} "
                f"institutional_blocks={len(institutional.content)} "
                f"briefing_blocks={len(briefing.content)} "
                f"events_blocks={len(events.content)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
