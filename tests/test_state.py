"""執行狀態的測試。"""

import json
import tempfile
import unittest
from pathlib import Path

from x_stock_tracker.state import StateStore


class TestStateStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_when_file_missing(self):
        state = StateStore(self.path)
        self.assertEqual(state.last_post_id, "")
        self.assertFalse(state.is_seen("1"))

    def test_mark_seen_tracks_highest_numeric_id(self):
        state = StateStore(self.path)
        state.mark_seen(["1800000000000000005", "1800000000000000002"])
        self.assertEqual(state.last_post_id, "1800000000000000005")
        self.assertTrue(state.is_seen("1800000000000000002"))

    def test_does_not_move_last_id_backwards(self):
        state = StateStore(self.path)
        state.mark_seen(["1800000000000000005"])
        state.mark_seen(["1800000000000000001"])
        self.assertEqual(state.last_post_id, "1800000000000000005")

    def test_roundtrip(self):
        state = StateStore(self.path)
        state.mark_seen(["123"])
        state.user_id = "U123"
        state.save()
        reloaded = StateStore(self.path)
        self.assertTrue(reloaded.is_seen("123"))
        self.assertEqual(reloaded.user_id, "U123")

    def test_corrupt_file_is_recoverable(self):
        self.path.write_text("{ not json", encoding="utf-8")
        state = StateStore(self.path)
        self.assertEqual(state.last_post_id, "")
        state.mark_seen(["7"])
        state.save()
        self.assertIn("7", json.loads(self.path.read_text(encoding="utf-8"))["seen_post_ids"])


if __name__ == "__main__":
    unittest.main()
