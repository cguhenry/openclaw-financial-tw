from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/api/health")
def get_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "stock-dashboard-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
