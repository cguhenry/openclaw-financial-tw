from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RuleType = Literal[
    "price_at_or_below",
    "price_at_or_above",
    "breakout",
    "breakdown",
    "range_entry",
]
AlertSide = Literal["buy", "sell"]
AlertSource = Literal["user", "ai-assisted"]


class AlertUpsertRequest(BaseModel):
    side: AlertSide
    rule_type: RuleType
    target_price: float = Field(gt=0)
    upper_price: float | None = Field(default=None, gt=0)
    cooldown_minutes: int = Field(default=120, ge=1, le=1440)
    source: AlertSource = "user"
    note: str | None = Field(default=None, max_length=400)
    enabled: bool = True
    delivery_channels: list[str] = Field(default_factory=list)
    delivery_targets: list[str] = Field(default_factory=list)


class AlertTestRequest(BaseModel):
    alert_id: str | None = None
    force_delivery: bool = False

