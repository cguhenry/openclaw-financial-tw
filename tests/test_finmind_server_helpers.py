import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp" / "finmind_server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("finmind_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FinMindServerHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = load_server()

    def test_yyyymmdd_to_iso_strips_non_digits(self):
        self.assertEqual(self.server._yyyymmdd_to_iso("2026/05/31"), "2026-05-31")
        self.assertEqual(self.server._yyyymmdd_to_iso("2026-05-31"), "2026-05-31")

    def test_fetch_dataset_keeps_most_recent_rows_in_order(self):
        payload = {
            "status": 200,
            "data": [
                {"date": "2026-06-01", "value": 1},
                {"date": "2026-06-02", "value": 2},
                {"date": "2026-06-03", "value": 3},
                {"date": "2026-06-04", "value": 4},
            ],
        }

        class FakeResponse:
            status_code = 200

            def json(self):
                return payload

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get(self, url, params=None):
                return FakeResponse()

        with patch.object(self.server.httpx, "Client", FakeClient), patch.object(self.server, "_finmind_token", return_value="test-token"):
            result = self.server._fetch_dataset("TaiwanStockPrice", "2330", "2026-06-01", max_rows=2)

        self.assertEqual(result["returned_rows"], 2)
        self.assertEqual([row["date"] for row in result["data"]], ["2026-06-03", "2026-06-04"])


if __name__ == "__main__":
    unittest.main()
