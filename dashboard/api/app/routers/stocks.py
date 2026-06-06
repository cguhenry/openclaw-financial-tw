from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..schemas.alerts import AlertTestRequest, AlertUpsertRequest
from ..services.alerts import alert_service
from ..services.market_data import (
    fetch_analysis_payload,
    fetch_chart_payload,
    fetch_institutional_payload,
    fetch_main_force_payload,
    fetch_multi_period_payload,
    fetch_pattern_payload,
    fetch_quote_payload,
    fetch_signal_payload,
    retrain_prediction_models,
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


@router.get("/{stock_id}/patterns")
def get_patterns(stock_id: str, force_refresh: bool = Query(default=False)) -> dict:
    try:
        return fetch_pattern_payload(_validate_stock_id(stock_id), force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/signals")
def get_signals(stock_id: str, force_refresh: bool = Query(default=False)) -> dict:
    try:
        return fetch_signal_payload(_validate_stock_id(stock_id), force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{stock_id}/refresh")
def refresh_stock(stock_id: str, limit: int = Query(default=120, ge=30, le=240)) -> dict:
    try:
        return refresh_stock_payload(_validate_stock_id(stock_id), limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{stock_id}/train-models")
def train_models(stock_id: str) -> dict:
    try:
        return retrain_prediction_models(_validate_stock_id(stock_id))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/alerts")
def get_alerts(stock_id: str) -> dict:
    try:
        return alert_service.list_alerts(_validate_stock_id(stock_id))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{stock_id}/alerts")
def create_alert(stock_id: str, payload: AlertUpsertRequest) -> dict:
    try:
        return alert_service.create_alert(_validate_stock_id(stock_id), payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.patch("/{stock_id}/alerts/{alert_id}")
def patch_alert(stock_id: str, alert_id: str, payload: AlertUpsertRequest) -> dict:
    try:
        return alert_service.patch_alert(_validate_stock_id(stock_id), alert_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{stock_id}/alerts/test")
def test_alert(stock_id: str, payload: AlertTestRequest) -> dict:
    try:
        return alert_service.test_alert(
            _validate_stock_id(stock_id),
            payload.alert_id,
            force_delivery=payload.force_delivery,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{stock_id}/ai-alert-preview")
def get_ai_alert_preview(stock_id: str) -> dict:
    try:
        return alert_service.build_ai_preview(_validate_stock_id(stock_id))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/notification-targets/import")
def import_notification_targets() -> dict:
    try:
        return alert_service.import_notification_targets()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
