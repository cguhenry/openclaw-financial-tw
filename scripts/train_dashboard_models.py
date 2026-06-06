#!/usr/bin/env python3
"""Offline trainer for dashboard prediction models."""

from __future__ import annotations

import argparse
import json
import sys

from dashboard.api.app.services.market_data import retrain_prediction_models


def main() -> int:
    parser = argparse.ArgumentParser(description="Train dashboard prediction models for one stock.")
    parser.add_argument("stock_id", help="Taiwan stock id, e.g. 2330")
    args = parser.parse_args()

    result = retrain_prediction_models(args.stock_id.strip().upper())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
