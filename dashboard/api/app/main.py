from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .services.alerts import alert_service
from .config import settings
from .routers.health import router as health_router
from .routers.stocks import router as stocks_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    alert_service.start_poller()
    try:
        yield
    finally:
        alert_service.stop_poller()


app = FastAPI(
    title="OpenClaw Financial TW Stock Dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(stocks_router)
