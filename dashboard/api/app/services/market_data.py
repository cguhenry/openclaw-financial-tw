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


def _start_date(days: int) -> str:
    return (_today_taipei().date() - timedelta(days=days)).isoformat()


def _net_from_row(row: dict[str, Any]) -> float:
    return float((row.get("buy") or 0) - (row.get("sell") or 0))


def _serialize_candle_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "time": str(row["time"]),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
                "turnover": int(row["turnover"]),
                "spread": round(float(row["close"]) - float(row["open"]), 2),
            }
        )
    return rows


def _build_weekly_candles(candles: list[dict[str, Any]], limit: int = 26) -> list[dict[str, Any]]:
    frame = _build_frame(candles).copy()
    frame["time"] = pd.to_datetime(frame["time"])
    weekly = (
        frame.set_index("time")
        .resample("W-FRI")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "turnover": "sum",
            }
        )
        .dropna()
        .reset_index()
    )
    weekly["time"] = weekly["time"].dt.date.astype(str)
    return _serialize_candle_frame(weekly.tail(limit))


def _price_change_pct(first_close: float, last_close: float) -> float:
    if not first_close:
        return 0.0
    return round(((last_close - first_close) / first_close) * 100, 2)


def _describe_kd_signal(k_value: float, d_value: float) -> str:
    if k_value >= 80 and d_value >= 80:
        return "高檔鈍化"
    if k_value <= 20 and d_value <= 20:
        return "低檔鈍化"
    if k_value > d_value:
        return "黃金交叉後偏多"
    if k_value < d_value:
        return "死亡交叉後偏弱"
    return "中性"


def _describe_macd_signal(dif_value: float, signal_value: float, hist_value: float) -> str:
    if dif_value > signal_value and hist_value > 0:
        return "多頭動能擴張"
    if dif_value > signal_value and hist_value <= 0:
        return "翻多初期"
    if dif_value < signal_value and hist_value < 0:
        return "空頭動能擴張"
    if dif_value < signal_value and hist_value >= 0:
        return "轉弱初期"
    return "中性"


def _compose_evaluation(
    *,
    trend_direction: str,
    ma_signal: str,
    bb_position: str,
    bb_channel: str,
    vol_price: str,
    kd_signal: str,
    macd_signal: str,
) -> str:
    if trend_direction == "多頭趨勢":
        if "偏熱" in bb_position and "量縮" in vol_price:
            return "股價仍在多方慣性內，但已貼近布林上緣且量能沒有同步放大，較像高檔續攻後的換手段，短線不適合追價，宜等回檔確認承接。"
        if "量增上漲" in vol_price and "開口擴大" in bb_channel and "多頭" in macd_signal:
            return "均線、量能與 MACD 同步支持多方，屬於趨勢延伸型走法；若後續拉回仍守住 MA20，偏向強勢整理而非轉弱。"
        return "價格結構仍由多方掌控，但短線節奏要看量能是否續強；若 KD 維持高檔而 MACD 沒有翻空，偏向多頭整理後再選方向。"

    if trend_direction == "空頭趨勢":
        if "偏弱" in bb_position and "空頭" in macd_signal:
            return "股價位在空方主導區，布林位置與 MACD 都偏弱，反彈較可能先視為跌深修正；未重新站回 MA20 前，不宜把短彈當成趨勢反轉。"
        if "量縮下跌" in vol_price and "低檔" in kd_signal:
            return "空方趨勢尚未解除，但賣壓有暫時收斂跡象，較像弱勢跌深整理；若後續量縮止穩，才有機會進入技術性反彈。"
        return "結構仍偏空，關鍵在支撐區是否失守；若量能重新放大且 MACD 持續擴大負值，弱勢段可能延續。"

    if "低檔" in kd_signal and "翻多" in macd_signal:
        return "目前偏向區間整理中的低位回穩，KD 與 MACD 有初步修復跡象，但還需要量能與 MA20 站穩來確認不是單日反彈。"
    if "高檔" in kd_signal and "轉弱" in macd_signal:
        return "價格暫時沒有脫離整理帶，但高檔指標已出現鈍化轉弱，短線容易先走震盪洗盤；若跌回回檔區下緣，結構會明顯轉差。"
    if "均線糾結" in ma_signal and "收斂" in bb_channel:
        return "均線糾結且布林收斂，典型等待突破的壓縮區。操作重點不在猜方向，而在觀察壓力區與支撐區哪一側先被有效突破。"
    return "技術面仍在整理區間內，現階段訊號彼此沒有完全共振。較穩健的做法是等待量價與 MACD/KD 同步表態後再決定是否進場。"


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

    kd_signal = _describe_kd_signal(latest_k, latest_d)
    macd_signal = _describe_macd_signal(latest_dif, latest_signal, latest_hist)
    evaluation = _compose_evaluation(
        trend_direction=trend_direction,
        ma_signal=ma_signal,
        bb_position=bb_position,
        bb_channel=bb_channel,
        vol_price=vol_price,
        kd_signal=kd_signal,
        macd_signal=macd_signal,
    )

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
            "signal": kd_signal,
        },
        {
            "name": "MACD",
            "values": f"DIF {latest_dif:.2f} / DEA {latest_signal:.2f}",
            "direction": "↑" if latest_dif > latest_signal else "↓",
            "signal": macd_signal,
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


def fetch_institutional_payload(stock_id: str, days: int = 10, force_refresh: bool = False) -> dict[str, Any]:
    safe_days = min(max(days, 5), 20)
    cache_key = f"institutional:{stock_id}:{safe_days}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    server = load_server_module()
    dataset = server.get_institutional_flows(stock_id, _start_date(safe_days * 4), max_rows=safe_days * 10)
    rows = dataset.get("data") or []
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("no institutional flow data available")

    frame["net"] = frame.apply(_net_from_row, axis=1)
    pivot = (
        frame.pivot_table(index="date", columns="name", values="net", aggfunc="sum", fill_value=0)
        .sort_index()
        .tail(safe_days)
        .reset_index()
    )

    normalized_rows: list[dict[str, Any]] = []
    for _, row in pivot.iterrows():
        foreign = int(row.get("Foreign_Investor", 0))
        trust = int(row.get("Investment_Trust", 0))
        dealer_self = int(row.get("Dealer_self", 0))
        dealer_hedging = int(row.get("Dealer_Hedging", 0))
        foreign_dealer = int(row.get("Foreign_Dealer_Self", 0))
        dealer_total = dealer_self + dealer_hedging + foreign_dealer
        total = foreign + trust + dealer_total
        normalized_rows.append(
            {
                "date": row["date"],
                "foreign": foreign,
                "investment_trust": trust,
                "dealer_total": dealer_total,
                "dealer_self": dealer_self,
                "dealer_hedging": dealer_hedging,
                "foreign_dealer_self": foreign_dealer,
                "total": total,
            }
        )

    recent = normalized_rows[-5:] if len(normalized_rows) >= 5 else normalized_rows
    summary = {
        "foreign_5d_net": sum(item["foreign"] for item in recent),
        "trust_5d_net": sum(item["investment_trust"] for item in recent),
        "dealer_5d_net": sum(item["dealer_total"] for item in recent),
        "total_5d_net": sum(item["total"] for item in recent),
    }
    result = {
        "stock": {
            "stock_id": stock_id,
            "name": stock_id,
        },
        "rows": normalized_rows,
        "summary": summary,
        "meta": {
            "source": dataset.get("source"),
            "dataset": dataset.get("dataset"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.analysis_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.analysis_ttl_seconds)


def fetch_main_force_payload(stock_id: str, days: int = 10, force_refresh: bool = False) -> dict[str, Any]:
    safe_days = min(max(days, 5), 20)
    cache_key = f"main-force:{stock_id}:{safe_days}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    method = "institutional_proxy"
    note = "Broker 分點資料目前未穩定可用，先以法人淨買超與外資持股變化作為主力 proxy。"

    institutional = fetch_institutional_payload(stock_id, days=safe_days, force_refresh=force_refresh)
    rows = institutional["rows"]
    foreign_holding_ratio = None
    foreign_holding_change = None
    try:
        server = load_server_module()
        holding = server.get_foreign_holding_pct(stock_id, _start_date(120), max_rows=2).get("data") or []
        if holding:
            foreign_holding_ratio = float(holding[-1].get("ForeignInvestmentSharesRatio") or 0)
        if len(holding) >= 2:
            current = float(holding[-1].get("ForeignInvestmentSharesRatio") or 0)
            previous = float(holding[-2].get("ForeignInvestmentSharesRatio") or 0)
            foreign_holding_change = round(current - previous, 2)
    except Exception:
        foreign_holding_ratio = None
        foreign_holding_change = None

    enriched_rows: list[dict[str, Any]] = []
    running = 0
    for item in rows:
        proxy_net = int(item["foreign"] + item["investment_trust"] + int(item["dealer_total"] * 0.5))
        running += proxy_net
        enriched_rows.append(
            {
                "date": item["date"],
                "proxy_net": proxy_net,
                "cumulative_net": running,
                "institutional_total": item["total"],
                "foreign": item["foreign"],
                "investment_trust": item["investment_trust"],
                "dealer_total": item["dealer_total"],
            }
        )

    recent_5d_net = sum(item["proxy_net"] for item in enriched_rows[-5:])
    recent_10d_net = sum(item["proxy_net"] for item in enriched_rows[-10:])
    recent_trend = sum(item["proxy_net"] for item in enriched_rows[-3:])

    if recent_10d_net > 0 and recent_trend > 0:
        signal = {"signal": "買超初期", "color": "green", "message": "法人 proxy 仍在增倉，短線偏多。"}
    elif recent_10d_net < 0 or recent_trend < 0:
        signal = {"signal": "出貨初期", "color": "red", "message": "法人 proxy 轉弱，需留意追價風險。"}
    else:
        signal = {"signal": "觀望期", "color": "yellow", "message": "主力方向未完全表態，先觀察關鍵價位。"}

    result = {
        "stock": institutional["stock"],
        "method": method,
        "note": note,
        "signal": signal,
        "rows": enriched_rows,
        "summary": {
            "recent_5d_net": recent_5d_net,
            "recent_10d_net": recent_10d_net,
            "foreign_holding_ratio": foreign_holding_ratio,
            "foreign_holding_change": foreign_holding_change,
        },
        "meta": {
            "source": institutional["meta"]["source"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.analysis_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.analysis_ttl_seconds)


def fetch_multi_period_payload(stock_id: str, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"multi-period:{stock_id}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    chart_payload = fetch_chart_payload(stock_id, timeframe="daily", limit=180, force_refresh=force_refresh)
    candles = chart_payload["candles"]
    short_daily = candles[-20:]
    daily = candles[-60:]
    weekly = _build_weekly_candles(candles, limit=26)

    def summarize(label: str, series: list[dict[str, Any]], note: str | None = None) -> dict[str, Any]:
        first_close = float(series[0]["close"])
        last_close = float(series[-1]["close"])
        return {
            "id": label,
            "label": label,
            "candles": series,
            "trend": "上行" if last_close > first_close else "下行" if last_close < first_close else "盤整",
            "change_pct": _price_change_pct(first_close, last_close),
            "last_close": last_close,
            "note": note,
        }

    result = {
        "stock": chart_payload["stock"],
        "periods": [
            summarize("短週期", short_daily, "以近 20 根日 K 觀察短線節奏，作為分鐘級資料接入前的替代視角。"),
            summarize("日K", daily, "觀察近 60 個交易日的主要波段。"),
            summarize("週K", weekly, "由日線重採樣，便於看中期結構。"),
        ],
        "meta": {
            "source": chart_payload["meta"]["source"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.chart_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.chart_ttl_seconds)


def refresh_stock_payload(stock_id: str, limit: int = 120) -> dict[str, Any]:
    CACHE.delete_prefix(f"quote:{stock_id}")
    CACHE.delete_prefix(f"chart:{stock_id}:")
    CACHE.delete_prefix(f"analysis:{stock_id}")
    CACHE.delete_prefix(f"institutional:{stock_id}:")
    CACHE.delete_prefix(f"main-force:{stock_id}:")
    CACHE.delete_prefix(f"multi-period:{stock_id}")
    return {
        "quote": fetch_quote_payload(stock_id, force_refresh=True),
        "chart": fetch_chart_payload(stock_id, timeframe="daily", limit=limit, force_refresh=True),
        "analysis": fetch_analysis_payload(stock_id, force_refresh=True),
        "institutional": fetch_institutional_payload(stock_id, force_refresh=True),
        "main_force": fetch_main_force_payload(stock_id, force_refresh=True),
        "multi_period": fetch_multi_period_payload(stock_id, force_refresh=True),
    }
