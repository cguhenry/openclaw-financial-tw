from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from ..cache import TTLCache
from ..config import settings


ROOT = Path(__file__).resolve().parents[4]
SERVER_PATH = ROOT / "mcp" / "finmind_server.py"
CACHE = TTLCache()


def _today_taipei() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


@lru_cache(maxsize=1)
def load_server_module() -> Any:
    spec = importlib.util.spec_from_file_location("finmind_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load MCP server from {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_stock_name(stock_id: str, quote_payload: dict[str, Any] | None) -> str:
    if quote_payload:
        name = quote_payload.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return stock_id


def fetch_quote_payload(stock_id: str, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"quote:{stock_id}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    server = load_server_module()
    payload = server.get_realtime_quote(stock_id)
    quote = payload["quote"]
    result = {
        "stock": {
            "stock_id": stock_id,
            "name": _resolve_stock_name(stock_id, quote),
        },
        "quote": {
            "price": quote.get("lastPrice") or quote.get("closePrice"),
            "change": quote.get("change"),
            "change_pct": quote.get("changePercent"),
            "volume": (quote.get("total") or {}).get("tradeVolume"),
            "trade_value": (quote.get("total") or {}).get("tradeValue"),
            "previous_close": quote.get("previousClose"),
            "open": quote.get("openPrice"),
            "high": quote.get("highPrice"),
            "low": quote.get("lowPrice"),
            "bid": ((quote.get("bids") or [{}])[0]).get("price"),
            "ask": ((quote.get("asks") or [{}])[0]).get("price"),
            "market": quote.get("market"),
            "exchange": quote.get("exchange"),
            "is_close": quote.get("isClose"),
            "last_updated": quote.get("lastUpdated"),
            "date": quote.get("date"),
        },
        "meta": {
            "source": payload.get("source"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.quote_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.quote_ttl_seconds)


def fetch_chart_payload(stock_id: str, timeframe: str = "daily", limit: int = 120, force_refresh: bool = False) -> dict[str, Any]:
    if timeframe != "daily":
        raise ValueError("Only daily timeframe is implemented in Phase 1")

    safe_limit = min(max(limit, 30), 240)
    cache_key = f"chart:{stock_id}:{timeframe}:{safe_limit}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    server = load_server_module()
    start_date = (_today_taipei().date() - timedelta(days=420)).isoformat()
    dataset = server.get_stock_price_daily(stock_id, start_date, max_rows=safe_limit)
    quote_payload = fetch_quote_payload(stock_id, force_refresh=force_refresh)
    candles = [
        {
            "time": row["date"],
            "open": row["open"],
            "high": row["max"],
            "low": row["min"],
            "close": row["close"],
            "volume": row["Trading_Volume"],
            "turnover": row["Trading_turnover"],
            "spread": row["spread"],
        }
        for row in dataset["data"]
        if row.get("date")
    ]
    result = {
        "stock": {
            "stock_id": stock_id,
            "name": quote_payload["stock"]["name"],
        },
        "timeframe": timeframe,
        "candles": candles,
        "meta": {
            "source": dataset.get("source"),
            "dataset": dataset.get("dataset"),
            "returned_rows": dataset.get("returned_rows"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.chart_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.chart_ttl_seconds)


def _build_frame(candles: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(candles)
    if frame.empty:
        raise ValueError("no candle data available")
    frame = frame.sort_values("time").reset_index(drop=True)
    return frame


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def fetch_analysis_payload(stock_id: str, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"analysis:{stock_id}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    chart_payload = fetch_chart_payload(stock_id, timeframe="daily", limit=180, force_refresh=force_refresh)
    candles = chart_payload["candles"]
    frame = _build_frame(candles)
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]

    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    bb_mid = ma20
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + bb_std * 2
    bb_lower = bb_mid - bb_std * 2

    low_9 = low.rolling(9).min()
    high_9 = high.rolling(9).max()
    k_fast = ((close - low_9) / (high_9 - low_9).replace(0, pd.NA)) * 100
    kd_k = k_fast.rolling(3).mean()
    kd_d = kd_k.rolling(3).mean()

    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd_dif = ema12 - ema26
    macd_signal = _ema(macd_dif, 9)
    macd_hist = macd_dif - macd_signal

    latest_close = float(close.iloc[-1])
    latest_ma5 = float(ma5.iloc[-1]) if pd.notna(ma5.iloc[-1]) else latest_close
    latest_ma20 = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else latest_close
    latest_ma60 = float(ma60.iloc[-1]) if pd.notna(ma60.iloc[-1]) else latest_close
    latest_bb_upper = float(bb_upper.iloc[-1]) if pd.notna(bb_upper.iloc[-1]) else latest_close
    latest_bb_lower = float(bb_lower.iloc[-1]) if pd.notna(bb_lower.iloc[-1]) else latest_close
    latest_bb_mid = float(bb_mid.iloc[-1]) if pd.notna(bb_mid.iloc[-1]) else latest_close
    latest_k = float(kd_k.iloc[-1]) if pd.notna(kd_k.iloc[-1]) else 50.0
    latest_d = float(kd_d.iloc[-1]) if pd.notna(kd_d.iloc[-1]) else 50.0
    latest_dif = float(macd_dif.iloc[-1]) if pd.notna(macd_dif.iloc[-1]) else 0.0
    latest_signal = float(macd_signal.iloc[-1]) if pd.notna(macd_signal.iloc[-1]) else 0.0
    latest_hist = float(macd_hist.iloc[-1]) if pd.notna(macd_hist.iloc[-1]) else 0.0

    latest_vol_ma5 = float(volume.rolling(5).mean().iloc[-1]) if pd.notna(volume.rolling(5).mean().iloc[-1]) else float(volume.iloc[-1])
    previous_vol_ma5 = float(volume.rolling(5).mean().iloc[-6]) if len(frame) > 6 and pd.notna(volume.rolling(5).mean().iloc[-6]) else latest_vol_ma5
    price_up_5d = bool(len(frame) > 5 and latest_close > float(close.iloc[-6]))
    vol_shrink = latest_vol_ma5 < previous_vol_ma5

    bb_width_now = latest_bb_upper - latest_bb_lower
    bb_width_prev = float((bb_upper.iloc[-6] - bb_lower.iloc[-6])) if len(frame) > 6 and pd.notna(bb_upper.iloc[-6]) and pd.notna(bb_lower.iloc[-6]) else bb_width_now
    bb_pct = 0.5 if bb_width_now == 0 else (latest_close - latest_bb_lower) / bb_width_now

    if latest_ma5 > latest_ma20 > latest_ma60:
        ma_signal = "多頭排列（5 > 20 > 60）"
    elif latest_ma5 < latest_ma20 < latest_ma60:
        ma_signal = "空頭排列（5 < 20 < 60）"
    else:
        ma_signal = "均線糾結（整理中）"

    if bb_pct > 0.9:
        bb_position = "貼近上軌（偏熱）"
    elif bb_pct < 0.1:
        bb_position = "貼近下軌（偏弱）"
    else:
        bb_position = "通道中段"

    bb_channel = "開口擴大（趨勢加速）" if bb_width_now > bb_width_prev * 1.02 else "開口收斂（整理）"

    if price_up_5d and vol_shrink:
        vol_price = "量縮上漲，動能降溫"
    elif price_up_5d and not vol_shrink:
        vol_price = "量增上漲，走勢強健"
    elif not price_up_5d and vol_shrink:
        vol_price = "量縮下跌，賣壓不重"
    else:
        vol_price = "量增下跌，賣壓偏重"

    if latest_close > latest_ma20 > latest_ma60:
        trend_direction = "多頭趨勢"
    elif latest_close < latest_ma20 < latest_ma60:
        trend_direction = "空頭趨勢"
    else:
        trend_direction = "橫盤整理"

    if trend_direction == "多頭趨勢" and bb_pct > 0.85 and vol_shrink:
        evaluation = "高檔震盪，追價風險升高"
    elif trend_direction == "多頭趨勢" and not vol_shrink:
        evaluation = "多頭延續，短線偏強"
    elif trend_direction == "空頭趨勢" and bb_pct < 0.2:
        evaluation = "弱勢區間，宜保守觀察"
    else:
        evaluation = "技術面中性，等待更明確方向"

    recent_high = float(high.tail(20).max())
    recent_low = float(low.tail(60).min())
    resistance = {"low": round(recent_high * 0.98, 2), "high": round(recent_high, 2)}
    support_anchor = min(recent_low, latest_bb_lower)
    support = {"low": round(support_anchor * 0.98, 2), "high": round(support_anchor * 1.02, 2)}
    swing_high = float(high.tail(60).max())
    swing_low = float(low.tail(60).min())
    fib_382 = swing_high - (swing_high - swing_low) * 0.382
    fib_618 = swing_high - (swing_high - swing_low) * 0.618
    pullback = {"low": round(fib_618, 2), "high": round(fib_382, 2)}

    indicator_summary = [
        {
            "name": "KD",
            "values": f"K {latest_k:.1f} / D {latest_d:.1f}",
            "direction": "↑" if latest_k > latest_d else "↓",
            "signal": "高檔鈍化" if latest_k > 80 else "低檔鈍化" if latest_k < 20 else "中性",
        },
        {
            "name": "MACD",
            "values": f"DIF {latest_dif:.2f} / DEA {latest_signal:.2f}",
            "direction": "↑" if latest_dif > latest_signal else "↓",
            "signal": "多頭延續" if latest_hist > 0 else "空頭偏弱",
        },
        {
            "name": "均線排列",
            "values": f"MA5 {latest_ma5:.1f} / MA20 {latest_ma20:.1f} / MA60 {latest_ma60:.1f}",
            "direction": "↑" if latest_ma5 > latest_ma20 else "↓" if latest_ma5 < latest_ma20 else "→",
            "signal": ma_signal,
        },
        {
            "name": "布林通道",
            "values": f"上 {latest_bb_upper:.1f} / 中 {latest_bb_mid:.1f} / 下 {latest_bb_lower:.1f}",
            "direction": "↑" if bb_channel.startswith("開口擴大") else "→",
            "signal": bb_channel,
        },
        {
            "name": "成交量",
            "values": f"今量 {int(volume.iloc[-1]):,} / 5日均量 {int(latest_vol_ma5):,}",
            "direction": "↑" if not vol_shrink else "↓",
            "signal": vol_price,
        },
    ]

    result = {
        "stock": chart_payload["stock"],
        "technical_summary": {
            "trend_direction": trend_direction,
            "price_position": bb_position,
            "ma_alignment": ma_signal,
            "vol_price_relation": vol_price,
            "bb_position": bb_position,
            "bb_channel": bb_channel,
            "composite_evaluation": evaluation,
        },
        "key_levels": {
            "resistance": resistance,
            "pullback": pullback,
            "support": support,
        },
        "indicator_summary": indicator_summary,
        "raw_indicators": {
            "kd": {"k": round(latest_k, 2), "d": round(latest_d, 2)},
            "macd": {"dif": round(latest_dif, 4), "signal": round(latest_signal, 4), "hist": round(latest_hist, 4)},
            "bollinger": {"upper": round(latest_bb_upper, 2), "mid": round(latest_bb_mid, 2), "lower": round(latest_bb_lower, 2), "pct": round(bb_pct, 4)},
        },
        "meta": {
            "source": chart_payload["meta"]["source"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.analysis_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.analysis_ttl_seconds)


def refresh_stock_payload(stock_id: str, limit: int = 120) -> dict[str, Any]:
    CACHE.delete_prefix(f"quote:{stock_id}")
    CACHE.delete_prefix(f"chart:{stock_id}:")
    CACHE.delete_prefix(f"analysis:{stock_id}")
    return {
        "quote": fetch_quote_payload(stock_id, force_refresh=True),
        "chart": fetch_chart_payload(stock_id, timeframe="daily", limit=limit, force_refresh=True),
        "analysis": fetch_analysis_payload(stock_id, force_refresh=True),
    }
