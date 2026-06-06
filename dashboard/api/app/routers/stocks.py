from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services.market_data import (
    fetch_analysis_payload,
    fetch_chart_payload,
    fetch_institutional_payload,
    fetch_main_force_payload,
    fetch_multi_period_payload,
    fetch_quote_payload,
    refresh_stock_payload,
)


router = APIRouter(prefix="/api/stocks", tags=["stocks"])


def _validate_stock_id(stock_id: str) -> str:
    normalized = stock_id.strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="stock_id is required")
    if len(normalized) > 10:
        raise HTTPException(status_code=400, detail="stock_id is too long")
    return normalized


@router.get("/{stock_id}/quote")
def get_quote(stock_id: str, force_refresh: bool = Query(default=False)) -> dict:
    try:
        return fetch_quote_payload(_validate_stock_id(stock_id), force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/chart")
def get_chart(
    stock_id: str,
    timeframe: str = Query(default="daily"),
    limit: int = Query(default=120, ge=30, le=240),
    force_refresh: bool = Query(default=False),
) -> dict:
    try:
        return fetch_chart_payload(
            _validate_stock_id(stock_id),
            timeframe=timeframe,
            limit=limit,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/analysis")
def get_analysis(stock_id: str, force_refresh: bool = Query(default=False)) -> dict:
    try:
        return fetch_analysis_payload(_validate_stock_id(stock_id), force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/institutional")
def get_institutional(
    stock_id: str,
    days: int = Query(default=10, ge=5, le=20),
    force_refresh: bool = Query(default=False),
) -> dict:
    try:
        return fetch_institutional_payload(_validate_stock_id(stock_id), days=days, force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/main-force")
def get_main_force(
    stock_id: str,
    days: int = Query(default=10, ge=5, le=20),
    force_refresh: bool = Query(default=False),
) -> dict:
    try:
        return fetch_main_force_payload(_validate_stock_id(stock_id), days=days, force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/multi-period")
def get_multi_period(stock_id: str, force_refresh: bool = Query(default=False)) -> dict:
    try:
        return fetch_multi_period_payload(_validate_stock_id(stock_id), force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{stock_id}/refresh")
def refresh_stock(stock_id: str, limit: int = Query(default=120, ge=30, le=240)) -> dict:
    try:
        return refresh_stock_payload(_validate_stock_id(stock_id), limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
