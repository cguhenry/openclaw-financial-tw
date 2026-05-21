#!/usr/bin/env python3
"""Verify Phase 0 Taiwan financial data source access without printing secrets."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body)


def check_finmind() -> tuple[bool, str]:
    token = os.getenv("FINMIND_TOKEN")
    if not token:
        return False, "FINMIND_TOKEN missing"

    params = urllib.parse.urlencode(
        {
            "dataset": "TaiwanStockPrice",
            "data_id": "2330",
            "start_date": "2026-05-01",
            "token": token,
        }
    )
    payload = fetch_json(f"https://api.finmindtrade.com/api/v4/data?{params}")
    rows = payload.get("data") or []
    if payload.get("status") != 200 or not rows:
        return False, f"unexpected response: status={payload.get('status')} rows={len(rows)}"
    return True, f"rows={len(rows)} first_date={rows[0].get('date')}"


def check_twse() -> tuple[bool, str]:
    payload = fetch_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
    if not isinstance(payload, list) or not payload:
        return False, "unexpected empty/non-list response"
    sample = next((row for row in payload if str(row.get("Code", "")) == "2330"), payload[0])
    return True, f"rows={len(payload)} sample={sample.get('Code')} {sample.get('Name')}"


def check_fugle() -> tuple[bool, str]:
    key = os.getenv("FUGLE_API_KEY")
    if not key:
        return False, "FUGLE_API_KEY missing"

    url = "https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/2330"
    payload = fetch_json(url, headers={"X-API-KEY": key})
    if not isinstance(payload, dict) or "symbol" not in payload:
        return False, f"unexpected response keys={sorted(payload)[:8] if isinstance(payload, dict) else type(payload).__name__}"
    return True, f"symbol={payload.get('symbol')} name={payload.get('name')}"


def main() -> int:
    checks = [
        ("finmind", check_finmind),
        ("twse", check_twse),
        ("fugle", check_fugle),
    ]
    failed = False
    for name, check in checks:
        try:
            ok, detail = check()
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        status = "OK" if ok else "FAIL"
        print(f"{name}: {status} - {detail}")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

