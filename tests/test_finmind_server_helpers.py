import importlib.util
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
