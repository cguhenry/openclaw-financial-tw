from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_host: str = os.getenv("DASHBOARD_API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("DASHBOARD_API_PORT", "9180"))
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv(
            "DASHBOARD_CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8080,http://localhost:8080",
        ).split(",")
        if item.strip()
    )
    quote_ttl_seconds: int = int(os.getenv("DASHBOARD_QUOTE_TTL_SECONDS", "20"))
    chart_ttl_seconds: int = int(os.getenv("DASHBOARD_CHART_TTL_SECONDS", "21600"))
    analysis_ttl_seconds: int = int(os.getenv("DASHBOARD_ANALYSIS_TTL_SECONDS", "300"))


settings = Settings()
