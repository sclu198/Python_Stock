"""設定腳本 scripts/telegram_get_chat_id.py 的測試（不連網）。"""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "telegram_get_chat_id.py"
spec = importlib.util.spec_from_file_location("telegram_setup", SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def response(status=200, payload=None):
    resp = mock.Mock(status_code=status, text="", content=b"{}")
    resp.json.return_value = payload if payload is not None else {"ok": True, "result": {}}
    return resp


class TestSaveEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / ".env"

    def tearDown(self):
        self.tmp.cleanup()

    def test_updates_existing_keys_in_place(self):
        self.path.write_text("NOTIFIER=line\nTELEGRAM_BOT_TOKEN=\nOTHER=keep\n", encoding="utf-8")
        setup._save_env({"NOTIFIER": "telegram", "TELEGRAM_BOT_TOKEN": "111:AAA"}, self.path)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("NOTIFIER=telegram", text)
        self.assertIn("TELEGRAM_BOT_TOKEN=111:AAA", text)
        self.assertIn("OTHER=keep", text)
        self.assertNotIn("NOTIFIER=line", text)

    def test_appends_missing_keys(self):
        self.path.write_text("OTHER=keep\n", encoding="utf-8")
        setup._save_env({"TELEGRAM_CHAT_ID": "123"}, self.path)
        self.assertIn("TELEGRAM_CHAT_ID=123", self.path.read_text(encoding="utf-8"))

    def test_does_not_duplicate_on_second_run(self):
        setup._save_env({"TELEGRAM_CHAT_ID": "123"}, self.path)
        setup._save_env({"TELEGRAM_CHAT_ID": "456"}, self.path)
        text = self.path.read_text(encoding="utf-8")
        self.assertEqual(text.count("TELEGRAM_CHAT_ID="), 1)
        self.assertIn("TELEGRAM_CHAT_ID=456", text)


class TestFindChats(unittest.TestCase):
    def test_extracts_chat_id_and_description(self):
        payload = {
            "ok": True,
            "result": [
                {"message": {"chat": {"id": 987654321, "type": "private", "username": "SCLU0215"}}},
                {"message": {"chat": {"id": 987654321, "type": "private", "username": "SCLU0215"}}},
            ],
        }
        with mock.patch.object(setup.requests, "get", return_value=response(payload=payload)):
            chats = setup._find_chats("111:AAA", 30)
        self.assertEqual(chats, {"987654321": "private @SCLU0215"})

    def test_empty_when_no_messages(self):
        with mock.patch.object(setup.requests, "get", return_value=response(payload={"ok": True, "result": []})):
            self.assertEqual(setup._find_chats("111:AAA", 30), {})


class TestMain(unittest.TestCase):
    def test_happy_path_sends_test_message(self):
        get_me = response(payload={"ok": True, "result": {"username": "BruceLu215Bot"}})
        updates = response(payload={
            "ok": True,
            "result": [{"message": {"chat": {"id": 987654321, "type": "private", "username": "SCLU0215"}}}],
        })
        with mock.patch.object(setup.requests, "get", side_effect=[get_me, updates]), \
             mock.patch.object(setup.requests, "post", return_value=response()) as post:
            code = setup.main(["--token", "111:AAA", "--no-test"])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_count, 0)

        with mock.patch.object(setup.requests, "get", side_effect=[get_me, updates]), \
             mock.patch.object(setup.requests, "post", return_value=response()) as post:
            code = setup.main(["--token", "111:AAA"])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args[1]["json"]["chat_id"], "987654321")

    def test_reports_when_user_has_not_pressed_start(self):
        get_me = response(payload={"ok": True, "result": {"username": "BruceLu215Bot"}})
        updates = response(payload={"ok": True, "result": []})
        with mock.patch.object(setup.requests, "get", side_effect=[get_me, updates]):
            self.assertEqual(setup.main(["--token", "111:AAA"]), 1)

    def test_bad_token_exits_nonzero(self):
        bad = response(401, {"ok": False, "description": "Unauthorized"})
        with mock.patch.object(setup.requests, "get", return_value=bad):
            self.assertEqual(setup.main(["--token", "wrong"]), 1)


if __name__ == "__main__":
    unittest.main()
