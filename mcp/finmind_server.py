#!/usr/bin/env python3
"""OpenClaw MCP server for FinMind Taiwan financial datasets."""

from __future__ import annotations

import os
import json
import logging
import re
import csv
import io
import time
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import httpx
from mcp.server.fastmcp import FastMCP


FINMIND_API = "https://api.finmindtrade.com/api/v4/data"
FUGLE_QUOTE_API = "https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote"
TWSE_HOME_NEWS_JSON = "https://www.twse.com.tw/res/data/zh/home/news.json"
TWSE_INSTITUTIONAL_SUMMARY_JSON = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&dayDate={date}&type=day"
MOPS_MAJOR_ANNOUNCEMENTS_PAGE = "https://mopsov.twse.com.tw/mops/web/t05sr01_1"
MOPS_MAJOR_ANNOUNCEMENTS_AJAX = "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1"
CBC_USD_NTD_DAILY_CSV = "https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData015.csv"
CBC_USD_NTD_MONTHLY_CSV = "https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData016.csv"
CBC_USD_NTD_YEARLY_CSV = "https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData017.csv"
CBC_POLICY_RATES_CSV = "https://www.cbc.gov.tw/public/data/OpenData/經研處/EG28D01.csv"
CBC_MONEY_SUPPLY_AVG_MONTHLY_CSV = "https://www.cbc.gov.tw/public/data/OpenData/經研處/EF15M01.csv"
CBC_MONEY_SUPPLY_EOP_MONTHLY_CSV = "https://www.cbc.gov.tw/public/data/OpenData/經研處/EF17M01.csv"
DGBAS_CPI_XML = "https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/230556/pr0104a1m.xml"
DGBAS_GDP_SDMX = "https://nstatdb.dgbas.gov.tw/dgbasAll/webMain.aspx?sdmx/A018101010/{indicators}...Q.&startTime={start_time}&endTime={end_time}"
DEFAULT_TIMEOUT = float(os.getenv("FINMIND_HTTP_TIMEOUT_SECONDS", "20"))
MAX_ROWS_DEFAULT = 500
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "9123"))
MCP_MOUNT_PATH = os.getenv("MCP_MOUNT_PATH", "/")
MCP_SSE_PATH = os.getenv("MCP_SSE_PATH", "/sse")
MCP_MESSAGE_PATH = os.getenv("MCP_MESSAGE_PATH", "/messages/")
MCP_STREAMABLE_HTTP_PATH = os.getenv("MCP_STREAMABLE_HTTP_PATH", "/mcp")
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")

mcp = FastMCP(
    "finmind-tw",
    host=MCP_HOST,
    port=MCP_PORT,
    mount_path=MCP_MOUNT_PATH,
    sse_path=MCP_SSE_PATH,
    message_path=MCP_MESSAGE_PATH,
    streamable_http_path=MCP_STREAMABLE_HTTP_PATH,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

MARKET_ALIASES = {
    "all": "all",
    "sii": "sii",
    "twse": "sii",
    "listed": "sii",
    "上市": "sii",
    "otc": "otc",
    "tpex": "otc",
    "上櫃": "otc",
    "rotc": "rotc",
    "emerging": "rotc",
    "興櫃": "rotc",
    "pub": "pub",
    "public": "pub",
    "公開發行": "pub",
}
MARKET_LABELS = {
    "all": "全體公司",
    "sii": "上市公司",
    "otc": "上櫃公司",
    "rotc": "興櫃公司",
    "pub": "公開發行公司",
}
DGBAS_GDP_FIELD_NAMES = {
    "1": "midyear_population",
    "2": "average_exchange_rate_ntd_usd",
    "3": "real_gdp_growth_pct",
    "4": "nominal_gdp_ntd_million",
    "5": "nominal_gdp_usd_million",
    "6": "nominal_gdp_per_capita_ntd",
    "7": "nominal_gdp_per_capita_usd",
    "8": "nominal_gni_ntd_million",
    "9": "nominal_gni_usd_million",
    "10": "nominal_gni_per_capita_ntd",
    "11": "nominal_gni_per_capita_usd",
    "12": "national_income_ntd_million",
    "13": "national_income_usd_million",
    "14": "national_income_per_capita_ntd",
    "15": "national_income_per_capita_usd",
}


class FinMindError(RuntimeError):
    """Raised when FinMind returns an unusable response."""


_dotenv_loaded: bool = False


def _load_dotenv() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)
    _dotenv_loaded = True


def _finmind_token() -> str:
    _load_dotenv()
    token = os.getenv("FINMIND_TOKEN")
    if not token:
        raise FinMindError("FINMIND_TOKEN is not configured")
    return token


def _fugle_api_key() -> str:
    _load_dotenv()
    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        raise FinMindError("FUGLE_API_KEY is not configured")
    return api_key


def _fetch_dataset(
    dataset: str,
    data_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    extra: dict[str, Any] | None = None,
    max_rows: int = MAX_ROWS_DEFAULT,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "dataset": dataset,
        "token": _finmind_token(),
    }
    if data_id:
        params["data_id"] = data_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if extra:
        params.update(extra)

    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.get(FINMIND_API, params=params)
        if response.status_code >= 400:
            raise FinMindError(f"FinMind HTTP {response.status_code} for dataset={dataset}")
        payload = response.json()

    status = payload.get("status")
    data = payload.get("data") or []
    if status not in (200, "200"):
        raise FinMindError(f"FinMind status={status}: {payload.get('msg') or payload.get('message')}")
    if not isinstance(data, list):
        raise FinMindError("FinMind returned non-list data")

    limited = data[:max_rows] if max_rows and max_rows > 0 else data
    return {
        "source": "FinMind",
        "dataset": dataset,
        "data_id": data_id,
        "start_date": start_date,
        "end_date": end_date,
        "row_count": len(data),
        "returned_rows": len(limited),
        "data": limited,
    }


def _fetch_fugle_quote(stock_id: str) -> dict[str, Any]:
    headers = {"X-API-KEY": _fugle_api_key()}
    url = f"{FUGLE_QUOTE_API}/{stock_id}"
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers) as client:
        response = client.get(url)
        if response.status_code >= 400:
            raise FinMindError(f"Fugle HTTP {response.status_code} for stock_id={stock_id}")
        payload = response.json()
    if not isinstance(payload, dict) or "symbol" not in payload:
        raise FinMindError("Fugle returned an unexpected quote payload")
    return {
        "source": "Fugle",
        "dataset": "intraday_quote",
        "stock_id": stock_id,
        "quote": payload,
    }


def _fetch_json(url: str) -> Any:
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.get(url)
        if response.status_code >= 400:
            raise FinMindError(f"HTTP {response.status_code} for url={url}")
        return response.json()


def _fetch_text(url: str, method: str = "GET", data: dict[str, Any] | None = None) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": MOPS_MAJOR_ANNOUNCEMENTS_PAGE,
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers, follow_redirects=True) as client:
                response = client.request(method, url, data=data)
                if response.status_code >= 400:
                    raise FinMindError(f"HTTP {response.status_code} for url={url}")
                return response.text
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise FinMindError(f"request failed for url={url}: {last_error}")


def _fetch_text_url(url: str, verify: bool = True) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True, verify=verify) as client:
                response = client.get(url)
                if response.status_code >= 400:
                    raise FinMindError(f"HTTP {response.status_code} for url={url}")
                response.encoding = response.encoding or "utf-8-sig"
                return response.text
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise FinMindError(f"request failed for url={url}: {last_error}")


def _fetch_json_url(url: str, verify: bool = True) -> Any:
    content = _fetch_text_url(url, verify=verify)
    try:
        return json.loads(content)
    except ValueError as exc:
        raise FinMindError(f"non-JSON response for url={url}") from exc


def _fetch_csv_rows(url: str) -> list[dict[str, str]]:
    content = _fetch_text_url(url).lstrip("﻿")
    return [dict(row) for row in csv.DictReader(io.StringIO(content))]


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.replace(",", "").strip()
    if not value or value == "-":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    parsed = _to_float(value)
    return int(parsed) if parsed is not None else None


def _yyyymmdd_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        return None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def _period_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d{4})M(\d{2})", value)
    if match:
        return f"{match.group(1)}-{match.group(2)}-01"
    match = re.fullmatch(r"(\d{4})", value)
    if match:
        return f"{match.group(1)}-01-01"
    return None


def _filter_by_iso_date(rows: list[dict[str, Any]], start_date: str | None, end_date: str | None) -> list[dict[str, Any]]:
    if not start_date and not end_date:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_date = row.get("date") or row.get("period_start")
        if not isinstance(row_date, str):
            continue
        if start_date and row_date < start_date:
            continue
        if end_date and row_date > end_date:
            continue
        filtered.append(row)
    return filtered


def _tail_limit(rows: list[dict[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    if not max_rows or max_rows <= 0:
        return rows
    return rows[-max_rows:]


def _parse_announcement_link(link: str) -> dict[str, str | None]:
    query = parse_qs(urlparse(link).query)
    return {
        "company_id": query.get("COMPANY_ID", [None])[0],
        "typek": query.get("TYPEK", [None])[0],
        "spoke_date": query.get("SPOKE_DATE", [None])[0],
        "spoke_time": query.get("SPOKE_TIME", [None])[0],
        "seq_no": query.get("SEQ_NO", [None])[0],
    }


def _format_unix_ts(ts: int | float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _normalize_market(market: str | None) -> str:
    normalized = MARKET_ALIASES.get((market or "all").strip().lower())
    if not normalized:
        allowed = ", ".join(sorted(MARKET_LABELS))
        raise FinMindError(f"unsupported market={market!r}; allowed markets: {allowed}")
    return normalized


def _strip_html(value: str, preserve_newlines: bool = False) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value)
    if preserve_newlines:
        value = re.sub(r"[ \t\r\f\v]+", " ", value)
        return re.sub(r"\n{3,}", "\n\n", value).strip()
    return re.sub(r"\s+", " ", value).strip()


def _roc_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{2,3})/(\d{1,2})/(\d{1,2})", value)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    return f"{year + 1911:04d}-{month:02d}-{day:02d}"


def _compact_time(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) < 6:
        digits = digits.zfill(6)
    return f"{digits[:2]}:{digits[2:4]}:{digits[4:6]}"


def _announcement_category(title: str | None) -> str:
    title = title or ""
    categories = [
        ("法說會", "investor_conference"),
        ("董事會", "board_resolution"),
        ("股東會", "shareholder_meeting"),
        ("庫藏股", "treasury_stock"),
        ("現金增資", "capital_increase"),
        ("取得", "asset_transaction"),
        ("處分", "asset_transaction"),
        ("發言人", "spokesperson"),
        ("股利", "dividend"),
        ("除息", "dividend"),
        ("財務報告", "financial_report"),
    ]
    for keyword, category in categories:
        if keyword in title:
            return category
    return "other"


def _detail_url(market: str, company_id: str, spoke_date: str, spoke_time: str, seq_no: str) -> str:
    return (
        f"{MOPS_MAJOR_ANNOUNCEMENTS_PAGE}?encodeURIComponent=1&TYPEK={market}"
        f"&step=1&firstin=true&COMPANY_ID={company_id}&SPOKE_DATE={spoke_date}"
        f"&SPOKE_TIME={spoke_time}&SEQ_NO={seq_no}"
    )


def _parse_mops_major_rows(html: str, market: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    row_pattern = re.compile(r"<tr class='(?:odd|even)'>(.*?)</tr>", re.S)
    cell_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
    for row_html in row_pattern.findall(html):
        cells = [_strip_html(cell) for cell in cell_pattern.findall(row_html)]
        if len(cells) < 5:
            continue
        onclick_match = re.search(r"onclick=\"([^\"]+)\"", row_html, re.S)
        onclick = onclick_match.group(1) if onclick_match else ""
        params = {
            name.lower(): value
            for name, value in re.findall(r"\.([A-Z_]+)\.value='([^']*)'", onclick)
        }
        company_id = cells[0]
        company_name = cells[1]
        roc_date = cells[2]
        local_time = cells[3]
        title = cells[4]
        spoke_date = params.get("spoke_date") or (re.sub(r"\D", "", _roc_date_to_iso(roc_date) or "") or None)
        spoke_time = params.get("spoke_time") or re.sub(r"\D", "", local_time)
        seq_no = params.get("seq_no") or ""
        rows.append(
            {
                "company_id": company_id,
                "company_name": company_name,
                "market": market,
                "market_label": MARKET_LABELS.get(market, market),
                "spoke_date_roc": roc_date,
                "spoke_date": spoke_date,
                "spoke_date_iso": _roc_date_to_iso(roc_date),
                "spoke_time": spoke_time,
                "spoke_time_local": _compact_time(local_time),
                "seq_no": seq_no,
                "skey": params.get("skey"),
                "title": title,
                "category": _announcement_category(title),
                "detail_url": _detail_url(market, company_id, spoke_date or "", spoke_time or "", seq_no),
            }
        )
    return rows


def _fetch_mops_major_announcements(market: str) -> list[dict[str, Any]]:
    data = {"encodeURIComponent": "1", "step": "0", "firstin": "true", "TYPEK": market}
    html = _fetch_text(MOPS_MAJOR_ANNOUNCEMENTS_AJAX, method="POST", data=data)
    rows = _parse_mops_major_rows(html, market)
    if rows or market != "all":
        return rows
    # The full page includes the same official table and is a useful fallback when Ajax changes.
    return _parse_mops_major_rows(_fetch_text(MOPS_MAJOR_ANNOUNCEMENTS_PAGE), market)


def _parse_mops_detail(html: str) -> dict[str, Any]:
    detail: dict[str, Any] = {}
    pairs = re.findall(
        r"<th class='tblHead'[^>]*>(.*?)</th>\s*<td class='odd'[^>]*>(.*?)</td>",
        html,
        re.S,
    )
    for label_html, value_html in pairs:
        label = _strip_html(label_html)
        value = _strip_html(value_html)
        if label:
            detail[label] = value
    description_match = re.search(r"<th class='tblHead'[^>]*>\s*說明\s*</th>\s*<td class='odd'[^>]*>(.*?)</td>", html, re.S)
    if description_match:
        detail["說明"] = _strip_html(description_match.group(1), preserve_newlines=True)
    fact_date_roc = detail.get("事實發生日")
    if not fact_date_roc:
        for label, value in detail.items():
            if "事實發生日" in label:
                fact_date_roc = value
                break
    clause = detail.get("符合條款")
    if not clause:
        for label, value in detail.items():
            if "符合條款" in label:
                clause = value
                break
    return {
        "sequence_no": detail.get("序號"),
        "speaker": detail.get("發言人"),
        "speaker_title": detail.get("發言人職稱"),
        "speaker_phone": detail.get("發言人電話"),
        "subject": detail.get("主旨"),
        "clause": clause,
        "fact_date_roc": fact_date_roc,
        "fact_date_iso": _roc_date_to_iso(fact_date_roc),
        "description": detail.get("說明"),
        "raw_fields": detail,
    }


def _enrich_mops_detail(row: dict[str, Any]) -> dict[str, Any]:
    html = _fetch_text(row["detail_url"])
    return {**row, "detail": _parse_mops_detail(html)}


def _fetch_twse_home_announcements(stock_id: str | None, market: str, limit: int) -> list[dict[str, Any]]:
    payload = _fetch_json(TWSE_HOME_NEWS_JSON)
    items = payload.get("instant")
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        link = item.get("link")
        if not isinstance(link, str):
            continue
        meta = _parse_announcement_link(link)
        item_market = meta["typek"] or "sii"
        if market != "all" and item_market != market:
            continue
        if stock_id and meta["company_id"] != stock_id:
            continue
        title = item.get("title") if isinstance(item.get("title"), str) else ""
        normalized.append(
            {
                "company_id": meta["company_id"],
                "company_name": title.split(" ", 1)[0] if title else None,
                "market": item_market,
                "market_label": MARKET_LABELS.get(item_market, item_market),
                "spoke_date": meta["spoke_date"],
                "spoke_time": meta["spoke_time"],
                "spoke_time_local": _compact_time(meta["spoke_time"]),
                "seq_no": meta["seq_no"],
                "title": title,
                "category": _announcement_category(title),
                "detail_url": link.replace("mops.twse.com.tw", "mopsov.twse.com.tw"),
                "published_at_utc": _format_unix_ts(item.get("date")),
            }
        )
    return normalized[:limit] if limit and limit > 0 else normalized


# ─── TWSE event helpers ───────────────────────────────────────────────────────

_DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日到(\d{1,2})月(\d{1,2})日")


def _parse_event_date_range(event: dict[str, Any]) -> tuple[str | None, str | None]:
    """Parse event date range from title/description.

    Handles both intra-year ("5月20日到5月22日") and cross-year
    ("12月20日到1月20日") ranges. Returns (start_date, end_date) as YYYY-MM-DD
    strings, or (None, None) if no date pattern is found.
    """
    text = f"{event.get('title', '')} {event.get('description', '')}"
    match = _DATE_RE.search(text)
    if not match:
        return None, None
    sm, sd, em, ed = (int(x) for x in match.groups())
    now = datetime.now(timezone.utc)
    year = now.year
    start = datetime(year, sm, sd)
    # If end month is earlier than start month, the range crosses a year boundary
    end = datetime(year + 1, em, ed) if em < sm else datetime(year, em, ed)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _is_event_expired(event: dict[str, Any]) -> bool:
    """Return True if the event's end date is before today."""
    _, end_str = _parse_event_date_range(event)
    if end_str is None:
        return False  # unparseable dates → include rather than silently drop
    end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    return end_date < datetime.now(timezone.utc).date()


def _fetch_twse_home_events(limit: int = 20) -> list[dict[str, Any]]:
    payload = _fetch_json(TWSE_HOME_NEWS_JSON)
    items = payload.get("events")
    if not isinstance(items, list):
        return []
    events: list[dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        events.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "tag": item.get("tagText"),
                "description": item.get("description"),
                "source": "TWSE",
            }
        )
    return events


@mcp.tool()
def get_stock_price_daily(stock_id: str, start_date: str, end_date: str | None = None, adjusted: bool = False, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock daily OHLCV prices from FinMind."""
    dataset = "TaiwanStockPriceAdj" if adjusted else "TaiwanStockPrice"
    return _fetch_dataset(dataset, stock_id, start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_income_statement(stock_id: str, start_date: str, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock income statement rows from FinMind."""
    return _fetch_dataset("TaiwanStockFinancialStatements", stock_id, start_date, max_rows=max_rows)


@mcp.tool()
def get_balance_sheet(stock_id: str, start_date: str, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock balance sheet rows from FinMind."""
    return _fetch_dataset("TaiwanStockBalanceSheet", stock_id, start_date, max_rows=max_rows)


@mcp.tool()
def get_cash_flow_statement(stock_id: str, start_date: str, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock cash flow statement rows from FinMind."""
    return _fetch_dataset("TaiwanStockCashFlowsStatement", stock_id, start_date, max_rows=max_rows)


@mcp.tool()
def get_month_revenue(stock_id: str, start_date: str, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock monthly revenue from FinMind."""
    return _fetch_dataset("TaiwanStockMonthRevenue", stock_id, start_date, max_rows=max_rows)


@mcp.tool()
def get_institutional_flows(stock_id: str, start_date: str, end_date: str | None = None, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan institutional investor buy/sell data from FinMind."""
    return _fetch_dataset("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_margin_short_sale(stock_id: str, start_date: str, end_date: str | None = None, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan margin purchase and short sale data from FinMind."""
    return _fetch_dataset("TaiwanStockMarginPurchaseShortSale", stock_id, start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_dividend_policy(stock_id: str, start_date: str = "2000-01-01", max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock dividend policy rows from FinMind."""
    return _fetch_dataset("TaiwanStockDividend", stock_id, start_date, max_rows=max_rows)


@mcp.tool()
def get_per_pbr(stock_id: str, start_date: str, end_date: str | None = None, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock PER/PBR/yield history from FinMind."""
    return _fetch_dataset("TaiwanStockPER", stock_id, start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_shareholding_dist(stock_id: str, start_date: str, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock shareholding distribution data from FinMind."""
    try:
        return _fetch_dataset("TaiwanStockHoldingSharesPer", stock_id, start_date, max_rows=max_rows)
    except FinMindError as exc:
        fallback = _fetch_dataset("TaiwanStockShareholding", stock_id, start_date, max_rows=max_rows)
        fallback["dataset_requested"] = "TaiwanStockHoldingSharesPer"
        fallback["fallback_reason"] = str(exc)
        fallback["note"] = "FinMind shareholding distribution endpoint was unavailable; returned foreign shareholding table as the closest currently verified shareholding dataset."
        return fallback


@mcp.tool()
def get_foreign_holding_pct(stock_id: str, start_date: str, end_date: str | None = None, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan foreign investor shareholding percentage data from FinMind."""
    return _fetch_dataset("TaiwanStockShareholding", stock_id, start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_broker_trading(stock_id: str, start_date: str, end_date: str | None = None, max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan broker branch trading daily report from FinMind."""
    return _fetch_dataset("TaiwanStockTradingDailyReport", stock_id, start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_realtime_quote(stock_id: str) -> dict[str, Any]:
    """Get Taiwan stock realtime intraday quote from Fugle."""
    return _fetch_fugle_quote(stock_id)


@mcp.tool()
def get_usd_ntd_rate(
    frequency: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    max_rows: int = 60,
) -> dict[str, Any]:
    """Get official CBC USD/NTD closing exchange rates.

    frequency: daily, monthly, or yearly.
    """
    frequency_key = frequency.strip().lower()
    urls = {
        "daily": CBC_USD_NTD_DAILY_CSV,
        "monthly": CBC_USD_NTD_MONTHLY_CSV,
        "yearly": CBC_USD_NTD_YEARLY_CSV,
    }
    if frequency_key not in urls:
        raise FinMindError("frequency must be one of: daily, monthly, yearly")
    rows: list[dict[str, Any]] = []
    for raw in _fetch_csv_rows(urls[frequency_key]):
        raw_date = raw.get("日期") or raw.get("期間")
        date = _yyyymmdd_to_iso(raw_date) or _period_to_iso(raw_date)
        rows.append(
            {
                "date": date,
                "raw_date": raw_date,
                "usd_ntd": _to_float(raw.get("NTD/USD")),
            }
        )
    filtered = _filter_by_iso_date(rows, start_date, end_date)
    limited = _tail_limit(filtered, max_rows)
    return {
        "source": "CBC",
        "dataset": "usd_ntd_closing_rate",
        "frequency": frequency_key,
        "start_date": start_date,
        "end_date": end_date,
        "row_count": len(filtered),
        "returned_rows": len(limited),
        "official_source": {"url": urls[frequency_key], "agency": "中央銀行"},
        "data": limited,
    }


@mcp.tool()
def get_interest_rates(max_rows: int = 60) -> dict[str, Any]:
    """Get official CBC policy rates: rediscount, secured loan, and short-term accommodation."""
    rows: list[dict[str, Any]] = []
    for raw in _fetch_csv_rows(CBC_POLICY_RATES_CSV):
        rows.append(
            {
                "date": _yyyymmdd_to_iso(raw.get("日")),
                "raw_date": raw.get("日"),
                "rediscount_rate_pct": _to_float(raw.get("重貼現(%)")),
                "secured_loan_accommodation_rate_pct": _to_float(raw.get("擔保放款融通(%)")),
                "short_term_accommodation_rate_pct": _to_float(raw.get("短期融通(%)")),
            }
        )
    limited = _tail_limit(rows, max_rows)
    return {
        "source": "CBC",
        "dataset": "policy_interest_rates",
        "row_count": len(rows),
        "returned_rows": len(limited),
        "official_source": {"url": CBC_POLICY_RATES_CSV, "agency": "中央銀行"},
        "data": limited,
    }


@mcp.tool()
def get_money_supply(
    measure: str = "M2",
    basis: str = "average",
    max_rows: int = 60,
) -> dict[str, Any]:
    """Get official CBC money supply monthly data for M1A, M1B, or M2.

    basis: average for daily average monthly data; end_of_period for month-end data.
    """
    normalized_measure = measure.strip().upper().replace("１", "1").replace("２", "2")
    if normalized_measure not in {"M1A", "M1B", "M2"}:
        raise FinMindError("measure must be one of: M1A, M1B, M2")
    normalized_basis = basis.strip().lower()
    urls = {
        "average": CBC_MONEY_SUPPLY_AVG_MONTHLY_CSV,
        "end_of_period": CBC_MONEY_SUPPLY_EOP_MONTHLY_CSV,
        "eop": CBC_MONEY_SUPPLY_EOP_MONTHLY_CSV,
    }
    if normalized_basis not in urls:
        raise FinMindError("basis must be one of: average, end_of_period")
    full_width = normalized_measure.replace("M", "Ｍ").replace("1", "１").replace("2", "２")
    rows: list[dict[str, Any]] = []
    for raw in _fetch_csv_rows(urls[normalized_basis]):
        value_key = next((key for key in raw if full_width in key and "原始值" in key and "貨幣總計數" in key), None)
        yoy_key = next((key for key in raw if full_width in key and "年增率" in key and "貨幣總計數" in key), None)
        rows.append(
            {
                "period": raw.get("期間"),
                "period_start": _period_to_iso(raw.get("期間")),
                "measure": normalized_measure,
                "basis": "end_of_period" if normalized_basis in {"end_of_period", "eop"} else "average",
                "value": _to_float(raw.get(value_key) if value_key else None),
                "yoy_pct": _to_float(raw.get(yoy_key) if yoy_key else None),
                "unit": "NTD million",
            }
        )
    limited = _tail_limit(rows, max_rows)
    return {
        "source": "CBC",
        "dataset": "money_supply",
        "measure": normalized_measure,
        "basis": "end_of_period" if normalized_basis in {"end_of_period", "eop"} else "average",
        "row_count": len(rows),
        "returned_rows": len(limited),
        "official_source": {"url": urls[normalized_basis], "agency": "中央銀行"},
        "data": limited,
    }


@mcp.tool()
def get_cpi_data(max_rows: int = 60) -> dict[str, Any]:
    """Get official DGBAS Taiwan CPI total-index monthly data."""
    xml_text = _fetch_text_url(DGBAS_CPI_XML, verify=False)
    root = ElementTree.fromstring(xml_text)
    by_period: dict[str, dict[str, Any]] = {}
    for obs in root.findall("Obs"):
        item = obs.findtext("Item") or ""
        period = obs.findtext("TIME_PERIOD")
        value_type = obs.findtext("TYPE") or ""
        if not period or not item.startswith("全體家庭、總指數"):
            continue
        row = by_period.setdefault(
            period,
            {
                "period": period,
                "period_start": _period_to_iso(period),
                "item": item,
                "frequency": obs.findtext("FREQ"),
            },
        )
        value = _to_float(obs.findtext("Item_VALUE"))
        if "年增率" in value_type:
            row["yoy_pct"] = value
        elif "原始值" in value_type:
            row["index"] = value
    rows = [by_period[key] for key in sorted(by_period)]
    limited = _tail_limit(rows, max_rows)
    return {
        "source": "DGBAS",
        "dataset": "cpi_total_index",
        "row_count": len(rows),
        "returned_rows": len(limited),
        "official_source": {"url": DGBAS_CPI_XML, "agency": "行政院主計總處"},
        "data": limited,
    }


@mcp.tool()
def get_gdp_data(start_time: str = "2018", end_time: str | None = None, max_rows: int = 40) -> dict[str, Any]:
    """Get official DGBAS quarterly national-income/GDP common indicators via SDMX-JSON.

    start_time accepts a year such as 2018. end_time accepts a quarter such as 2026-Q1;
    defaults to the current quarter when omitted.
    """
    if end_time is None:
        now = datetime.now(timezone.utc)
        q = (now.month - 1) // 3 + 1
        end_time = f"{now.year}-Q{q}"
    indicators = "+".join(str(i) for i in range(1, 16))
    url = DGBAS_GDP_SDMX.format(indicators=indicators, start_time=start_time, end_time=end_time)
    payload = _fetch_json_url(url, verify=False)
    data = payload.get("data") or {}
    structure = data.get("structure") or {}
    dimensions = structure.get("dimensions") or {}
    series_dims = dimensions.get("series") or []
    obs_dims = dimensions.get("observation") or []
    if not series_dims or not obs_dims:
        raise FinMindError("DGBAS GDP SDMX response missing dimensions")

    indicator_values = series_dims[0].get("values") or []
    observation_values = obs_dims[0].get("values") or []
    indicator_by_index = {str(index): item for index, item in enumerate(indicator_values)}
    periods = {str(index): item for index, item in enumerate(observation_values)}

    rows_by_period: dict[str, dict[str, Any]] = {}
    datasets = data.get("dataSets") or []
    if not datasets:
        raise FinMindError("DGBAS GDP SDMX response missing dataSets")
    series = datasets[0].get("series") or {}
    for series_index, series_payload in series.items():
        indicator = indicator_by_index.get(str(series_index))
        if not indicator:
            continue
        indicator_id = str(indicator.get("id"))
        field_name = DGBAS_GDP_FIELD_NAMES.get(indicator_id, f"indicator_{indicator_id}")
        for obs_index, obs_value in (series_payload.get("observations") or {}).items():
            period = periods.get(str(obs_index))
            if not period:
                continue
            period_id = period.get("id")
            row = rows_by_period.setdefault(
                period_id,
                {
                    "period": period_id,
                    "period_label": period.get("name"),
                },
            )
            row[field_name] = obs_value[0] if obs_value else None

    rows = [rows_by_period[key] for key in sorted(rows_by_period)]
    limited = _tail_limit(rows, max_rows)
    return {
        "source": "DGBAS",
        "dataset": "national_income_common_gdp_indicators",
        "start_time": start_time,
        "end_time": end_time,
        "row_count": len(rows),
        "returned_rows": len(limited),
        "official_source": {
            "url": url,
            "agency": "行政院主計總處",
            "dataflow": "A018101010",
            "format": "SDMX-JSON",
        },
        "data": limited,
    }


@mcp.tool()
def get_exdividend_result(stock_id: str, start_date: str = "2015-01-01", max_rows: int = 500) -> dict[str, Any]:
    """Get Taiwan stock ex-dividend result table (除權除息結果表) from FinMind.

    Returns actual cash/stock dividend amounts, reference price, and fill/no-fill status
    for each ex-dividend event. Useful for chip-analysis and yield verification.
    """
    return _fetch_dataset("TaiwanStockDividendResult", stock_id, start_date, max_rows=max_rows)


@mcp.tool()
def get_taiex_index(start_date: str, end_date: str | None = None, max_rows: int = 500) -> dict[str, Any]:
    """Get TAIEX market price index daily history (加權指數, price-only, not total-return) from FinMind.

    Use get_taiex_total_return_index for the reinvestment-adjusted version.
    """
    return _fetch_dataset("TaiwanStockMarketIndex", "TAIEX", start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_taiex_total_return_index(start_date: str, end_date: str | None = None, max_rows: int = 500) -> dict[str, Any]:
    """Get TAIEX total-return index history from FinMind."""
    return _fetch_dataset("TaiwanStockTotalReturnIndex", "TAIEX", start_date, end_date, max_rows=max_rows)


@mcp.tool()
def get_us_market_context(symbols: str = "SPY,QQQ,SOXX", lookback_days: int = 21) -> dict[str, Any]:
    """Get recent US ETF moves from FinMind for Taiwan morning-briefing read-through."""
    start_date = (datetime.now(timezone.utc).date() - timedelta(days=lookback_days)).isoformat()
    data: list[dict[str, Any]] = []
    for symbol in [part.strip().upper() for part in symbols.split(",") if part.strip()]:
        result = _fetch_dataset("USStockPrice", symbol, start_date, max_rows=10)
        rows = result["data"]
        latest = rows[-1] if rows else {}
        previous = rows[-2] if len(rows) >= 2 else {}
        latest_close = latest.get("Close")
        previous_close = previous.get("Close")
        daily_return_pct = None
        if isinstance(latest_close, (int, float)) and isinstance(previous_close, (int, float)) and previous_close:
            daily_return_pct = (latest_close / previous_close - 1) * 100
        data.append(
            {
                "symbol": symbol,
                "latest_date": latest.get("date"),
                "latest_close": latest_close,
                "previous_close": previous_close,
                "daily_return_pct": daily_return_pct,
                "row_count": result["row_count"],
            }
        )
    return {
        "source": "FinMind",
        "dataset": "us_market_context",
        "symbols": symbols,
        "start_date": start_date,
        "row_count": len(data),
        "returned_rows": len(data),
        "data": data,
    }


@mcp.tool()
def get_institutional_market_summary(date: str | None = None, lookback_days: int = 7) -> dict[str, Any]:
    """Get TWSE market-wide three-institution buy/sell amount summary.

    date is YYYYMMDD. If omitted or unavailable, searches backward up to lookback_days.
    """
    base_date = datetime.now(timezone.utc).date()
    if date:
        base_date = datetime.strptime(date, "%Y%m%d").date()
    last_payload: dict[str, Any] | None = None
    for offset in range(max(lookback_days, 1)):
        day = base_date - timedelta(days=offset)
        query_date = day.strftime("%Y%m%d")
        url = TWSE_INSTITUTIONAL_SUMMARY_JSON.format(date=query_date)
        payload = _fetch_json_url(url)
        last_payload = payload
        if payload.get("stat") != "OK":
            continue
        rows = []
        for row in payload.get("data") or []:
            if len(row) < 4:
                continue
            rows.append(
                {
                    "name": row[0],
                    "buy_amount_ntd": _to_int(row[1]),
                    "sell_amount_ntd": _to_int(row[2]),
                    "net_amount_ntd": _to_int(row[3]),
                }
            )
        if rows:
            return {
                "source": "TWSE",
                "dataset": "institutional_market_summary",
                "date": payload.get("date") or query_date,
                "title": payload.get("title"),
                "row_count": len(rows),
                "returned_rows": len(rows),
                "official_source": {"url": url, "agency": "臺灣證券交易所"},
                "data": rows,
            }
    raise FinMindError(f"TWSE institutional summary unavailable after {lookback_days} days: {last_payload}")


@mcp.tool()
def get_investor_conference_events(limit: int = 20) -> dict[str, Any]:
    """Get upcoming TWSE homepage events filtered for investor conferences or results presentations.

    Expired events (end date before today) are silently removed, including any
    cross-year ranges such as "12月20日到1月20日" (2026-12-20 → 2027-01-20).
    """
    events = _fetch_twse_home_events(limit=limit * 2 if limit and limit > 0 else 40)
    # Filter out expired events first (before keyword filter so we don't waste slots)
    upcoming = [e for e in events if not _is_event_expired(e)]
    filtered = [
        event
        for event in upcoming
        if any(keyword in f"{event.get('title') or ''} {event.get('tag') or ''}"
               for keyword in ("法說", "業績發表", "投資人"))
    ]
    limited = filtered[:limit] if limit and limit > 0 else filtered
    return {
        "source": "TWSE",
        "dataset": "investor_conference_events",
        "row_count": len(filtered),
        "returned_rows": len(limited),
        "official_source": {"url": TWSE_HOME_NEWS_JSON, "agency": "臺灣證券交易所"},
        "data": limited,
    }


@mcp.tool()
def get_tw_market_briefing(announcement_limit: int = 8) -> dict[str, Any]:
    """Build a compact Taiwan market briefing dataset for morning-note style workflows."""
    today = datetime.now(timezone.utc).date()
    taiex_start = (today - timedelta(days=45)).isoformat()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            "usd_ntd": pool.submit(get_usd_ntd_rate, max_rows=1),
            "policy_rates": pool.submit(get_interest_rates, max_rows=1),
            "m2": pool.submit(get_money_supply, measure="M2", max_rows=1),
            "cpi": pool.submit(get_cpi_data, max_rows=1),
            "gdp": pool.submit(get_gdp_data, max_rows=1),
            "us_market": pool.submit(get_us_market_context),
            "institutional": pool.submit(get_institutional_market_summary),
            "taiex": pool.submit(get_taiex_total_return_index, taiex_start, max_rows=10),
            "announcements": pool.submit(get_major_announcements, limit=announcement_limit, summary_count=min(announcement_limit, 5)),
            "events": pool.submit(get_investor_conference_events, limit=5),
        }
        results: dict[str, Any] = {}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:  # noqa: BLE001
                logging.warning("get_tw_market_briefing: source %r failed: %s", name, exc)
                results[name] = {"_error": str(exc), "data": [], "summary": [], "row_count": 0, "returned_rows": 0}
    macro = {
        "usd_ntd": results["usd_ntd"]["data"],
        "policy_rates": results["policy_rates"]["data"],
        "m2": results["m2"]["data"],
        "cpi": results["cpi"]["data"],
        "gdp": results["gdp"]["data"],
    }
    errors = {
        name: result["_error"]
        for name, result in results.items()
        if isinstance(result, dict) and result.get("_error")
    }
    return {
        "source": "OpenClaw Taiwan Financial MCP",
        "dataset": "tw_market_briefing",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "macro": macro,
        "us_market_context": results["us_market"]["data"],
        "institutional_market_summary": results["institutional"]["data"],
        "taiex_total_return_index": results["taiex"]["data"],
        "major_announcements_summary": results["announcements"]["summary"],
        "investor_conference_events": results["events"]["data"],
        "errors": errors,
        "official_sources": {
            "cbc": [CBC_USD_NTD_DAILY_CSV, CBC_POLICY_RATES_CSV, CBC_MONEY_SUPPLY_AVG_MONTHLY_CSV],
            "dgbas_cpi": DGBAS_CPI_XML,
            "dgbas_gdp_sdmx": DGBAS_GDP_SDMX,
            "twse_home": TWSE_HOME_NEWS_JSON,
            "twse_institutional_summary": TWSE_INSTITUTIONAL_SUMMARY_JSON,
            "finmind_dataset": "TaiwanStockTotalReturnIndex",
        },
    }


@mcp.tool()
def get_equity_research_snapshot(stock_id: str, start_date: str | None = None) -> dict[str, Any]:
    """Collect core datasets for a first-pass Taiwan equity research report.

    start_date defaults to one year ago when omitted, giving 4 quarters of context.
    All sub-fetches run in parallel to minimise wall-clock latency.
    """
    if start_date is None:
        start_date = (datetime.now(timezone.utc).date() - timedelta(days=365)).isoformat()

    snapshot_meta: dict[str, Any] = {
        "source": "OpenClaw Taiwan Financial MCP",
        "dataset": "tw_equity_research_snapshot",
        "stock_id": stock_id,
        "start_date": start_date,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    with ThreadPoolExecutor(max_workers=7) as pool:
        futures = {
            "price": pool.submit(get_stock_price_daily, stock_id, start_date, max_rows=20),
            "per_pbr": pool.submit(get_per_pbr, stock_id, start_date, max_rows=20),
            "monthly_revenue": pool.submit(get_month_revenue, stock_id, start_date, max_rows=12),
            "income_statement": pool.submit(get_income_statement, stock_id, start_date, max_rows=20),
            "balance_sheet": pool.submit(get_balance_sheet, stock_id, start_date, max_rows=20),
            "cash_flow_statement": pool.submit(get_cash_flow_statement, stock_id, start_date, max_rows=20),
            "institutional_flows": pool.submit(get_institutional_flows, stock_id, start_date, max_rows=20),
            "major_announcements": pool.submit(get_major_announcements, stock_id=stock_id, limit=5, summary_count=5),
        }
        snapshot = dict(snapshot_meta)
        for name, future in futures.items():
            try:
                snapshot[name] = future.result()
            except Exception as exc:  # noqa: BLE001
                logging.warning("get_equity_research_snapshot[%s]: %s failed: %s", stock_id, name, exc)
                snapshot[name] = {"_error": str(exc), "data": [], "row_count": 0, "returned_rows": 0}
    return snapshot


@mcp.tool()
def get_major_announcements(
    stock_id: str | None = None,
    market: str = "all",
    limit: int = 20,
    summary_count: int = 5,
    include_details: bool = False,
) -> dict[str, Any]:
    """Get recent official MOPS major announcements.

    Args:
        stock_id: Optional Taiwan company stock ID, e.g. "2330".
        market: Market filter: all, sii/TWSE/listed, otc/TPEx, rotc/emerging, or pub.
        limit: Maximum full rows returned.
        summary_count: Number of compact headline rows to return under summary.
        include_details: Fetch each row's official MOPS detail page and add speaker, clause,
            fact date, and description fields. Use with small limits because it performs one
            extra official-site request per row.

    Official source:
    - MOPS realtime major announcements: https://mopsov.twse.com.tw/mops/web/t05sr01_1
    - MOPS Ajax endpoint used by the same page: https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1
    - TWSE homepage instant feed remains a fallback for outage tolerance.
    """
    normalized_market = _normalize_market(market)
    rows = _fetch_mops_major_announcements(normalized_market)
    source = "MOPS"
    dataset = "realtime_major_announcements"
    if not rows:
        rows = _fetch_twse_home_announcements(stock_id, normalized_market, limit)
        source = "TWSE"
        dataset = "homepage_instant_major_announcements"

    if stock_id:
        rows = [row for row in rows if row.get("company_id") == stock_id]

    limited = rows[:limit] if limit and limit > 0 else rows
    if include_details:
        limited = [_enrich_mops_detail(row) for row in limited]

    summary_limit = max(summary_count, 0)
    summary = [
        {
            "company_id": row.get("company_id"),
            "company_name": row.get("company_name"),
            "market": row.get("market"),
            "time": row.get("spoke_time_local"),
            "category": row.get("category"),
            "title": row.get("title"),
        }
        for row in limited[:summary_limit]
    ]
    return {
        "source": source,
        "dataset": dataset,
        "stock_id": stock_id,
        "market": normalized_market,
        "market_label": MARKET_LABELS.get(normalized_market, normalized_market),
        "row_count": len(rows),
        "returned_rows": len(limited),
        "summary_count": len(summary),
        "official_source": {
            "mops_page": MOPS_MAJOR_ANNOUNCEMENTS_PAGE,
            "mops_ajax": MOPS_MAJOR_ANNOUNCEMENTS_AJAX,
            "twse_fallback_feed": TWSE_HOME_NEWS_JSON,
            "market_typek": {
                "all": "全體公司",
                "sii": "上市公司",
                "otc": "上櫃公司",
                "rotc": "興櫃公司",
                "pub": "公開發行公司",
            },
            "note": "Rows come from the official MOPS realtime major-announcements table whenever available; detail_url points to the official announcement detail page.",
        },
        "summary": summary,
        "data": limited,
    }


if __name__ == "__main__":
    mcp.run(transport=MCP_TRANSPORT)
