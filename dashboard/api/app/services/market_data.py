from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ..cache import TTLCache
from ..config import settings


ROOT = Path(__file__).resolve().parents[4]
SERVER_PATH = ROOT / "mcp" / "finmind_server.py"
MODELS_DIR = ROOT / "dashboard" / "api" / "models"
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


def _ensure_models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR


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
    safe_limit = min(max(limit, 5 if timeframe == "60min" else 30), 240)
    cache_key = f"chart:{stock_id}:{timeframe}:{safe_limit}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    quote_payload = fetch_quote_payload(stock_id, force_refresh=force_refresh)
    if timeframe == "daily":
        server = load_server_module()
        start_date = (_today_taipei().date() - timedelta(days=420)).isoformat()
        dataset = server.get_stock_price_daily(stock_id, start_date, max_rows=safe_limit)
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
    elif timeframe == "60min":
        dataset = _fetch_fugle_intraday_candles(stock_id, timeframe="60")
        candles = [
            {
                "time": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "turnover": 0,
                "spread": round(float(row["close"]) - float(row["open"]), 2),
            }
            for row in dataset["data"]
        ][-safe_limit:]
    elif timeframe == "weekly":
        daily_payload = fetch_chart_payload(stock_id, timeframe="daily", limit=180, force_refresh=force_refresh)
        candles = _build_weekly_candles(daily_payload["candles"], limit=min(safe_limit, 52))
        dataset = {
            "source": daily_payload["meta"]["source"],
            "dataset": "weekly_from_daily_resample",
            "returned_rows": len(candles),
        }
    else:
        raise ValueError("Unsupported timeframe")
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


def _fetch_fugle_intraday_candles(stock_id: str, timeframe: str = "60") -> dict[str, Any]:
    server = load_server_module()
    key = server._fugle_api_key()
    timeout = getattr(server, "DEFAULT_TIMEOUT", 20)
    headers = {"X-API-KEY": key}
    url = f"https://api.fugle.tw/marketdata/v1.0/stock/intraday/candles/{stock_id}"
    with server.httpx.Client(timeout=timeout, headers=headers) as client:
        response = client.get(url, params={"timeframe": timeframe})
        if response.status_code >= 400:
            raise RuntimeError(f"Fugle intraday candles HTTP {response.status_code} for stock_id={stock_id}")
        payload = response.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError("Fugle intraday candles returned an unexpected payload")
    return {
        "source": "Fugle",
        "dataset": f"intraday_candles_{timeframe}",
        "returned_rows": len(payload.get("data") or []),
        "data": payload.get("data") or [],
        "date": payload.get("date"),
    }


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


def _find_local_extrema(values: list[float], order: int = 3) -> tuple[list[int], list[int]]:
    highs: list[int] = []
    lows: list[int] = []
    for index in range(order, len(values) - order):
        window = values[index - order : index + order + 1]
        center = values[index]
        if center == max(window) and window.count(center) == 1:
            highs.append(index)
        if center == min(window) and window.count(center) == 1:
            lows.append(index)
    return highs, lows


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


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


def _detect_patterns(frame: pd.DataFrame) -> dict[str, Any]:
    recent = frame.tail(60).reset_index(drop=True)
    highs = recent["high"].astype(float).tolist()
    lows = recent["low"].astype(float).tolist()
    closes = recent["close"].astype(float).tolist()
    high_idx, low_idx = _find_local_extrema(closes, order=3)

    w_bottom = {
        "formed": False,
        "stage": "等待低點結構",
        "l1_price": None,
        "l2_price": None,
        "neckline": None,
        "breakout": False,
        "reason": "近 60 根資料內尚未形成可辨識雙底。",
    }
    if len(low_idx) >= 2:
        l1_idx, l2_idx = low_idx[-2], low_idx[-1]
        l1 = lows[l1_idx]
        l2 = lows[l2_idx]
        neckline = max(highs[l1_idx:l2_idx + 1]) if l2_idx > l1_idx else highs[l2_idx]
        diff_pct = abs(l1 - l2) / max(l1, 1)
        breakout = closes[-1] > neckline
        if diff_pct <= 0.035:
            w_bottom = {
                "formed": breakout,
                "stage": "突破頸線" if breakout else "等待突破",
                "l1_price": round(l1, 2),
                "l2_price": round(l2, 2),
                "neckline": round(neckline, 2),
                "breakout": breakout,
                "reason": "雙底低點高度接近，已具備 W 底輪廓。" if not breakout else "已向上突破頸線，W 底型態成立。",
            }
        else:
            w_bottom = {
                "formed": False,
                "stage": "低點未對稱",
                "l1_price": round(l1, 2),
                "l2_price": round(l2, 2),
                "neckline": round(neckline, 2),
                "breakout": breakout,
                "reason": "兩個低點落差過大，暫不視為有效 W 底。",
            }

    m_top = {
        "formed": False,
        "stage": "等待高點結構",
        "h1_price": None,
        "h2_price": None,
        "neckline": None,
        "breakdown": False,
        "reason": "近 60 根資料內尚未形成可辨識雙頭。",
    }
    if len(high_idx) >= 2:
        h1_idx, h2_idx = high_idx[-2], high_idx[-1]
        h1 = highs[h1_idx]
        h2 = highs[h2_idx]
        neckline = min(lows[h1_idx:h2_idx + 1]) if h2_idx > h1_idx else lows[h2_idx]
        diff_pct = abs(h1 - h2) / max(h1, 1)
        breakdown = closes[-1] < neckline
        if diff_pct <= 0.035:
            m_top = {
                "formed": breakdown,
                "stage": "跌破頸線" if breakdown else "等待跌破",
                "h1_price": round(h1, 2),
                "h2_price": round(h2, 2),
                "neckline": round(neckline, 2),
                "breakdown": breakdown,
                "reason": "雙頭高度接近，已具備 M 頭輪廓。" if not breakdown else "已跌破頸線，M 頭型態成立。",
            }
        else:
            m_top = {
                "formed": False,
                "stage": "高點未對稱",
                "h1_price": round(h1, 2),
                "h2_price": round(h2, 2),
                "neckline": round(neckline, 2),
                "breakdown": breakdown,
                "reason": "兩個高點差距過大，暫不視為有效 M 頭。",
            }

    dominant = "none"
    if w_bottom["formed"]:
        dominant = "w_bottom"
    elif m_top["formed"]:
        dominant = "m_top"
    elif w_bottom["stage"] != "等待低點結構":
        dominant = "w_bottom_setup"
    elif m_top["stage"] != "等待高點結構":
        dominant = "m_top_setup"

    return {
        "w_bottom": w_bottom,
        "m_top": m_top,
        "dominant_pattern": dominant,
    }


def _generate_trading_suggestion(
    *,
    last_close: float,
    summary: dict[str, Any],
    levels: dict[str, Any],
    patterns: dict[str, Any],
) -> dict[str, Any]:
    resistance_high = levels["resistance"]["high"]
    pullback_low = levels["pullback"]["low"]
    support_low = levels["support"]["low"]

    if patterns["w_bottom"]["formed"]:
        strategy = "型態已轉強，可優先觀察突破後回測頸線是否守穩。"
        risk_note = "若跌回頸線下方且量縮失敗，需防假突破。"
    elif patterns["m_top"]["formed"]:
        strategy = "型態已轉弱，反彈較偏減碼而非追進。"
        risk_note = "若重新站回頸線上方，空方訊號會明顯鈍化。"
    elif summary["trend_direction"] == "多頭趨勢" and "偏熱" in summary["bb_position"]:
        strategy = "不追高，等待回檔到回檔區或 MA20 附近再觀察承接。"
        risk_note = "高檔量縮時，短線洗盤機率上升。"
    elif summary["trend_direction"] == "空頭趨勢":
        strategy = "先觀察支撐區是否止穩，未止穩前不急著攤平。"
        risk_note = "空方慣性未消失前，反彈容易受壓。"
    else:
        strategy = "以區間交易思路看待，等待關鍵價位被有效突破。"
        risk_note = "沒有量價共振前，訊號容易反覆。"

    return {
        "strategy": strategy,
        "breakout_condition": f"有效站上 {resistance_high:.2f} 並伴隨量能放大，再視為突破成立。",
        "pullback_plan": f"若回檔至 {pullback_low:.2f} 上方止穩，可觀察是否出現重新轉強訊號。",
        "stop_loss": f"跌破 {support_low:.2f} 且無法快速收復時，視為結構轉弱。",
        "risk_note": risk_note,
        "last_close": round(last_close, 2),
    }


def _build_forecast_skeleton(analysis_payload: dict[str, Any], pattern_payload: dict[str, Any], main_force_payload: dict[str, Any]) -> dict[str, Any]:
    summary = analysis_payload["technical_summary"]
    indicators = {item["name"]: item for item in analysis_payload["indicator_summary"]}
    score = 50.0

    if summary["trend_direction"] == "多頭趨勢":
        score += 10
    elif summary["trend_direction"] == "空頭趨勢":
        score -= 10

    if "黃金交叉" in indicators["KD"]["signal"] or "低檔" in indicators["KD"]["signal"]:
        score += 6
    elif "死亡交叉" in indicators["KD"]["signal"] or "高檔鈍化" in indicators["KD"]["signal"]:
        score -= 6

    if "多頭" in indicators["MACD"]["signal"] or "翻多" in indicators["MACD"]["signal"]:
        score += 8
    elif "空頭" in indicators["MACD"]["signal"] or "轉弱" in indicators["MACD"]["signal"]:
        score -= 8

    if main_force_payload["summary"]["recent_5d_net"] > 0:
        score += 6
    elif main_force_payload["summary"]["recent_5d_net"] < 0:
        score -= 6

    if pattern_payload["dominant_pattern"] == "w_bottom":
        score += 10
    elif pattern_payload["dominant_pattern"] == "m_top":
        score -= 10

    score = _clamp(score, 15, 85)
    down_pct = round(_clamp(100 - score - 18, 10, 70), 1)
    sideways_pct = round(max(5.0, 100 - score - down_pct), 1)
    up_pct = round(100 - down_pct - sideways_pct, 1)

    if up_pct >= down_pct and up_pct >= sideways_pct:
        prediction = "up"
        prediction_label = "偏多"
    elif down_pct >= up_pct and down_pct >= sideways_pct:
        prediction = "down"
        prediction_label = "偏空"
    else:
        prediction = "sideways"
        prediction_label = "震盪"

    win_rate = round(_clamp(score + 5, 20, 88), 1)
    confidence = round(max(up_pct, down_pct, sideways_pct), 1)

    return {
        "win_rate": {
            "value": win_rate,
            "label": "短線勝率",
            "basis": "rule_based_skeleton",
            "note": "此數值目前由技術指標、主力 proxy 與型態規則合成，屬於 API 骨架，後續可替換成實際模型。",
        },
        "direction_prediction": {
            "prediction": prediction,
            "prediction_label": prediction_label,
            "up_pct": up_pct,
            "down_pct": down_pct,
            "sideways_pct": sideways_pct,
            "confidence": confidence,
            "basis": "rule_based_skeleton",
            "note": "本階段先提供透明可追溯的 rule-based 機率分配，非訓練後機器學習模型。",
        },
    }


def _fetch_historical_daily_frame(stock_id: str, years: int = 4) -> pd.DataFrame:
    server = load_server_module()
    start = (_today_taipei().date() - timedelta(days=365 * years)).isoformat()
    dataset = server.get_stock_price_daily(stock_id, start, max_rows=1600)
    frame = pd.DataFrame(dataset.get("data") or [])
    if frame.empty:
        raise ValueError("no historical price data available")
    frame = frame.rename(
        columns={
            "date": "time",
            "max": "high",
            "min": "low",
            "Trading_Volume": "volume",
            "Trading_turnover": "turnover",
        }
    )
    return frame[["time", "open", "high", "low", "close", "volume", "turnover"]].sort_values("time").reset_index(drop=True)


def _fetch_historical_institutional_frame(stock_id: str, years: int = 4) -> pd.DataFrame:
    server = load_server_module()
    start = (_today_taipei().date() - timedelta(days=365 * years)).isoformat()
    dataset = server.get_institutional_flows(stock_id, start, max_rows=8000)
    rows = dataset.get("data") or []
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["time", "inst_total_net", "foreign_net", "trust_net", "dealer_net"])
    frame["net"] = frame.apply(_net_from_row, axis=1)
    pivot = frame.pivot_table(index="date", columns="name", values="net", aggfunc="sum", fill_value=0).sort_index().reset_index()
    pivot["foreign_net"] = pivot.get("Foreign_Investor", 0)
    pivot["trust_net"] = pivot.get("Investment_Trust", 0)
    pivot["dealer_net"] = pivot.get("Dealer_self", 0) + pivot.get("Dealer_Hedging", 0) + pivot.get("Foreign_Dealer_Self", 0)
    pivot["inst_total_net"] = pivot["foreign_net"] + pivot["trust_net"] + pivot["dealer_net"]
    pivot = pivot.rename(columns={"date": "time"})
    return pivot[["time", "inst_total_net", "foreign_net", "trust_net", "dealer_net"]]


def _build_feature_frame(price_frame: pd.DataFrame, institutional_frame: pd.DataFrame) -> pd.DataFrame:
    frame = price_frame.copy()
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    volume = frame["volume"].astype(float)

    frame["return_1d"] = close.pct_change(1)
    frame["return_3d"] = close.pct_change(3)
    frame["return_5d"] = close.pct_change(5)
    frame["volatility_5d"] = close.pct_change().rolling(5).std()
    frame["range_pct"] = (high - low) / close.replace(0, np.nan)

    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    frame["ma5_gap"] = (close - ma5) / ma5
    frame["ma20_gap"] = (close - ma20) / ma20
    frame["ma60_gap"] = (close - ma60) / ma60

    bb_std = close.rolling(20).std()
    bb_upper = ma20 + bb_std * 2
    bb_lower = ma20 - bb_std * 2
    frame["bb_pct"] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    low_9 = low.rolling(9).min()
    high_9 = high.rolling(9).max()
    k_fast = ((close - low_9) / (high_9 - low_9).replace(0, np.nan)) * 100
    kd_k = k_fast.rolling(3).mean()
    kd_d = kd_k.rolling(3).mean()
    frame["kd_k"] = kd_k / 100
    frame["kd_d"] = kd_d / 100

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_dif = ema12 - ema26
    macd_signal = macd_dif.ewm(span=9, adjust=False).mean()
    frame["macd_dif"] = macd_dif
    frame["macd_signal"] = macd_signal
    frame["macd_hist"] = macd_dif - macd_signal

    frame["volume_ratio_5d"] = volume / volume.rolling(5).mean()

    merged = frame.merge(institutional_frame, on="time", how="left").fillna(0)
    merged["inst_total_net_5d"] = merged["inst_total_net"].rolling(5).sum()
    merged["foreign_net_5d"] = merged["foreign_net"].rolling(5).sum()
    merged["dealer_net_5d"] = merged["dealer_net"].rolling(5).sum()

    merged["win_label"] = (merged["close"].shift(-5) > merged["close"]).astype(int)
    future_ret = merged["close"].shift(-1) / merged["close"] - 1
    merged["direction_label"] = 2
    merged.loc[future_ret > 0.015, "direction_label"] = 1
    merged.loc[future_ret < -0.015, "direction_label"] = 0
    return merged.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)


def _model_path(stock_id: str) -> Path:
    return _ensure_models_dir() / f"{stock_id}_prediction.joblib"


def train_prediction_models(stock_id: str) -> dict[str, Any]:
    feature_names = [
        "return_1d",
        "return_3d",
        "return_5d",
        "volatility_5d",
        "range_pct",
        "ma5_gap",
        "ma20_gap",
        "ma60_gap",
        "bb_pct",
        "kd_k",
        "kd_d",
        "macd_dif",
        "macd_signal",
        "macd_hist",
        "volume_ratio_5d",
        "inst_total_net_5d",
        "foreign_net_5d",
        "dealer_net_5d",
    ]
    price_frame = _fetch_historical_daily_frame(stock_id, years=4)
    institutional_frame = _fetch_historical_institutional_frame(stock_id, years=4)
    frame = _build_feature_frame(price_frame, institutional_frame)
    if len(frame) < 160:
        raise ValueError("not enough historical rows to train prediction models")

    split = max(int(len(frame) * 0.8), len(frame) - 120)
    split = min(max(split, 100), len(frame) - 20)
    train = frame.iloc[:split]
    test = frame.iloc[split:]

    X_train = train[feature_names]
    X_test = test[feature_names]

    win_model = RandomForestClassifier(
        n_estimators=240,
        max_depth=6,
        min_samples_leaf=4,
        random_state=42,
        class_weight="balanced_subsample",
    )
    direction_model = RandomForestClassifier(
        n_estimators=320,
        max_depth=7,
        min_samples_leaf=4,
        random_state=42,
        class_weight="balanced_subsample",
    )
    win_model.fit(X_train, train["win_label"])
    direction_model.fit(X_train, train["direction_label"])

    win_accuracy = float((win_model.predict(X_test) == test["win_label"]).mean())
    direction_accuracy = float((direction_model.predict(X_test) == test["direction_label"]).mean())

    package = {
        "stock_id": stock_id,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feature_names": feature_names,
        "metrics": {
            "win_accuracy": round(win_accuracy, 4),
            "direction_accuracy": round(direction_accuracy, 4),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
        },
        "win_model": win_model,
        "direction_model": direction_model,
        "latest_frame": frame.tail(120).to_dict(orient="records"),
    }
    joblib.dump(package, _model_path(stock_id))
    return package


def _load_prediction_package(stock_id: str) -> dict[str, Any]:
    path = _model_path(stock_id)
    if not path.exists():
        return train_prediction_models(stock_id)
    return joblib.load(path)


def _predict_with_models(stock_id: str, main_force_payload: dict[str, Any], pattern_payload: dict[str, Any]) -> dict[str, Any]:
    package = _load_prediction_package(stock_id)
    feature_names = package["feature_names"]

    price_frame = _fetch_historical_daily_frame(stock_id, years=4)
    institutional_frame = _fetch_historical_institutional_frame(stock_id, years=4)
    frame = _build_feature_frame(price_frame, institutional_frame)
    latest = frame.iloc[[-1]].copy()
    X_latest = latest[feature_names]

    win_model = package["win_model"]
    direction_model = package["direction_model"]
    win_rate = round(float(win_model.predict_proba(X_latest)[0][1]) * 100, 1)
    direction_proba = direction_model.predict_proba(X_latest)[0]
    classes = list(direction_model.classes_)
    probs = {int(cls): float(prob) for cls, prob in zip(classes, direction_proba)}
    down_pct = round(probs.get(0, 0.0) * 100, 1)
    up_pct = round(probs.get(1, 0.0) * 100, 1)
    sideways_pct = round(probs.get(2, 0.0) * 100, 1)

    predicted_class = max(probs.items(), key=lambda item: item[1])[0]
    prediction_map = {0: ("down", "偏空"), 1: ("up", "偏多"), 2: ("sideways", "震盪")}
    prediction, prediction_label = prediction_map[predicted_class]
    confidence = round(max(up_pct, down_pct, sideways_pct), 1)

    if pattern_payload["dominant_pattern"] == "w_bottom":
        up_pct = round(min(95.0, up_pct + 3.0), 1)
    elif pattern_payload["dominant_pattern"] == "m_top":
        down_pct = round(min(95.0, down_pct + 3.0), 1)

    if main_force_payload["summary"]["recent_5d_net"] > 0:
        win_rate = round(min(92.0, win_rate + 2.0), 1)
    elif main_force_payload["summary"]["recent_5d_net"] < 0:
        win_rate = round(max(8.0, win_rate - 2.0), 1)

    residual = round(max(0.0, 100 - up_pct - down_pct), 1)
    sideways_pct = residual if residual else sideways_pct

    return {
        "win_rate": {
            "value": win_rate,
            "label": "短線勝率",
            "basis": "trained_random_forest",
            "note": "使用近 4 年日線、技術指標與法人流向訓練而成，可離線重訓。",
            "metrics": package["metrics"],
            "trained_at": package["trained_at"],
        },
        "direction_prediction": {
            "prediction": prediction,
            "prediction_label": prediction_label,
            "up_pct": up_pct,
            "down_pct": down_pct,
            "sideways_pct": sideways_pct,
            "confidence": confidence,
            "basis": "trained_random_forest",
            "note": "使用隨機森林三分類模型預測下一交易日方向，可透過 train-models 端點或腳本離線重訓。",
            "metrics": package["metrics"],
            "trained_at": package["trained_at"],
        },
    }


def _fetch_broker_daily_report(stock_id: str, date: str) -> list[dict[str, Any]]:
    server = load_server_module()
    token = server._finmind_token()
    url = "https://api.finmindtrade.com/api/v4/taiwan_stock_trading_daily_report"
    headers = {"Authorization": f"Bearer {token}"}
    with server.httpx.Client(timeout=getattr(server, "DEFAULT_TIMEOUT", 20), headers=headers) as client:
        response = client.get(url, params={"data_id": stock_id, "date": date})
        if response.status_code >= 400:
            raise RuntimeError(response.text[:300])
        payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("unexpected broker trading payload")
    return payload["data"]


def _extract_broker_row_metrics(row: dict[str, Any]) -> tuple[str | None, float | None]:
    broker_keys = [
        "securities_trader",
        "securities_trader_id",
        "broker_id",
        "broker",
        "securities_company",
        "branch",
        "branch_name",
        "securities_trader_name",
    ]
    broker = next((str(row[key]).strip() for key in broker_keys if row.get(key)), None)
    buy_keys = ["buy", "buy_volume", "buy_shares", "buy_qty"]
    sell_keys = ["sell", "sell_volume", "sell_shares", "sell_qty"]
    buy_value = next((row[key] for key in buy_keys if row.get(key) is not None), None)
    sell_value = next((row[key] for key in sell_keys if row.get(key) is not None), None)
    if broker is None or buy_value is None or sell_value is None:
        return None, None
    return broker, float(buy_value) - float(sell_value)


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
            "last_close": round(latest_close, 2),
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

    method = "institutional_proxy"
    note = "Broker 分點資料目前未穩定可用，先以法人淨買超與外資持股變化作為主力 proxy。"
    enriched_rows: list[dict[str, Any]] = []

    try:
        broker_rows_by_date: list[tuple[str, list[dict[str, Any]]]] = []
        for item in rows:
            broker_rows_by_date.append((item["date"], _fetch_broker_daily_report(stock_id, item["date"])))

        running = 0
        for item, broker_rows in zip(rows, broker_rows_by_date, strict=False):
            date_value, payload_rows = broker_rows
            broker_scores: dict[str, float] = {}
            for raw_row in payload_rows:
                broker, net_value = _extract_broker_row_metrics(raw_row)
                if broker is None or net_value is None:
                    continue
                broker_scores[broker] = broker_scores.get(broker, 0.0) + net_value
            if not broker_scores:
                raise RuntimeError("broker dataset missing expected columns")
            top_n_sum = int(sum(value for _, value in sorted(broker_scores.items(), key=lambda pair: pair[1], reverse=True)[:20]))
            running += top_n_sum
            item_row = next(row for row in rows if row["date"] == date_value)
            enriched_rows.append(
                {
                    "date": date_value,
                    "proxy_net": top_n_sum,
                    "cumulative_net": running,
                    "institutional_total": item_row["total"],
                    "foreign": item_row["foreign"],
                    "investment_trust": item_row["investment_trust"],
                    "dealer_total": item_row["dealer_total"],
                }
            )
        method = "broker_top20"
        note = "已使用 FinMind sponsor 分點資料，依每日前 20 大淨買超券商加總計算主力進出。"
    except Exception as exc:
        running = 0
        enriched_rows = []
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
        note = "Broker 分點資料未啟用或權限不足，已退回法人 proxy。細節：" + str(exc)[:120]

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


def fetch_pattern_payload(stock_id: str, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"pattern:{stock_id}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    chart_payload = fetch_chart_payload(stock_id, timeframe="daily", limit=180, force_refresh=force_refresh)
    frame = _build_frame(chart_payload["candles"])
    result = {
        "stock": chart_payload["stock"],
        "patterns": _detect_patterns(frame),
        "meta": {
            "source": chart_payload["meta"]["source"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.analysis_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.analysis_ttl_seconds)


def fetch_signal_payload(stock_id: str, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"signal:{stock_id}"
    if not force_refresh:
        cached = CACHE.get(cache_key)
        if cached is not None:
            return cached

    analysis_payload = fetch_analysis_payload(stock_id, force_refresh=force_refresh)
    pattern_payload = fetch_pattern_payload(stock_id, force_refresh=force_refresh)
    main_force_payload = fetch_main_force_payload(stock_id, force_refresh=force_refresh)

    suggestion = _generate_trading_suggestion(
        last_close=analysis_payload["technical_summary"].get("last_close", 0) or analysis_payload["key_levels"]["pullback"]["high"],
        summary=analysis_payload["technical_summary"],
        levels=analysis_payload["key_levels"],
        patterns=pattern_payload["patterns"],
    )
    try:
        forecast = _predict_with_models(stock_id, main_force_payload, pattern_payload["patterns"])
    except Exception:
        forecast = _build_forecast_skeleton(analysis_payload, pattern_payload["patterns"], main_force_payload)

    result = {
        "stock": analysis_payload["stock"],
        "pattern_analysis": pattern_payload["patterns"],
        "trading_suggestion": suggestion,
        "win_rate": forecast["win_rate"],
        "direction_prediction": forecast["direction_prediction"],
        "meta": {
            "source": analysis_payload["meta"]["source"],
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
    intraday_60 = fetch_chart_payload(stock_id, timeframe="60min", limit=12, force_refresh=force_refresh)
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
            summarize("60分K", intraday_60["candles"], "使用 Fugle intraday candles 的真 60 分鐘資料。"),
            summarize("日K", daily, "觀察近 60 個交易日的主要波段。"),
            summarize("週K", weekly, "由日線重採樣，便於看中期結構。"),
        ],
        "meta": {
            "source": intraday_60["meta"]["source"] + " / " + chart_payload["meta"]["source"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": settings.chart_ttl_seconds,
        },
    }
    return CACHE.set(cache_key, result, settings.chart_ttl_seconds)


def retrain_prediction_models(stock_id: str) -> dict[str, Any]:
    package = train_prediction_models(stock_id)
    return {
        "stock_id": stock_id,
        "trained_at": package["trained_at"],
        "metrics": package["metrics"],
        "model_path": str(_model_path(stock_id)),
    }


def refresh_stock_payload(stock_id: str, limit: int = 120) -> dict[str, Any]:
    CACHE.delete_prefix(f"quote:{stock_id}")
    CACHE.delete_prefix(f"chart:{stock_id}:")
    CACHE.delete_prefix(f"analysis:{stock_id}")
    CACHE.delete_prefix(f"institutional:{stock_id}:")
    CACHE.delete_prefix(f"main-force:{stock_id}:")
    CACHE.delete_prefix(f"multi-period:{stock_id}")
    CACHE.delete_prefix(f"pattern:{stock_id}")
    CACHE.delete_prefix(f"signal:{stock_id}")
    return {
        "quote": fetch_quote_payload(stock_id, force_refresh=True),
        "chart": fetch_chart_payload(stock_id, timeframe="daily", limit=limit, force_refresh=True),
        "analysis": fetch_analysis_payload(stock_id, force_refresh=True),
        "institutional": fetch_institutional_payload(stock_id, force_refresh=True),
        "main_force": fetch_main_force_payload(stock_id, force_refresh=True),
        "multi_period": fetch_multi_period_payload(stock_id, force_refresh=True),
        "patterns": fetch_pattern_payload(stock_id, force_refresh=True),
        "signals": fetch_signal_payload(stock_id, force_refresh=True),
    }
