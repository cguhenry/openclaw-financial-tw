import importlib.util
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "tw_morning_briefing.py"


def load_script():
    spec = importlib.util.spec_from_file_location("tw_morning_briefing", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MorningBriefingRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script()

    def test_render_briefing_surfaces_failed_sources(self):
        payload = {
            "generated_at_utc": "2026-05-31T23:30:00+00:00",
            "macro": {
                "usd_ntd": [],
                "policy_rates": [],
                "m2": [],
                "cpi": [],
                "gdp": [],
            },
            "taiex_total_return_index": [],
            "us_market_context": [],
            "institutional_market_summary": [],
            "major_announcements_summary": [],
            "investor_conference_events": [],
            "errors": {
                "gdp": "timeout",
                "announcements": "upstream 500",
            },
        }

        rendered = self.script.render_briefing(payload)

        self.assertIn("部分資料來源暫時無法取得", rendered)
        self.assertIn("GDP: timeout", rendered)
        self.assertIn("重大訊息: upstream 500", rendered)

    def test_deliveries_from_env_parses_comma_separated_targets(self):
        previous = os.environ.get("TW_MORNING_DELIVERIES")
        try:
            os.environ["TW_MORNING_DELIVERIES"] = "discord:user:1, line:U123"
            self.assertEqual(
                self.script.deliveries_from_env(),
                ["discord:user:1", "line:U123"],
            )
        finally:
            if previous is None:
                os.environ.pop("TW_MORNING_DELIVERIES", None)
            else:
                os.environ["TW_MORNING_DELIVERIES"] = previous


if __name__ == "__main__":
    unittest.main()
