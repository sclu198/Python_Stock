"""Telegram 推播的測試（不連網）。"""

import unittest
from unittest import mock

from x_stock_tracker.config import Config
from x_stock_tracker.notify import NotifyError, build_notifier
from x_stock_tracker.notify.telegram import TelegramNotifier


def config(chat_id="123456789", notifier="telegram"):
    return Config(notifier=notifier, telegram_bot_token="111:AAA", telegram_chat_id=chat_id)


def fake_response(status=200, payload=None):
    resp = mock.Mock(status_code=status, text="")
    resp.json.return_value = payload if payload is not None else {"ok": True, "result": {}}
    return resp


class TestBuildNotifier(unittest.TestCase):
    def test_telegram_is_the_default(self):
        self.assertEqual(Config().notifier, "telegram")
        self.assertIsInstance(build_notifier(config()), TelegramNotifier)

    def test_unknown_notifier_raises(self):
        with self.assertRaises(NotifyError):
            build_notifier(config(notifier="carrier-pigeon"))


class TestTelegramNotifier(unittest.TestCase):
    def test_sends_expected_payload(self):
        notifier = TelegramNotifier(config())
        with mock.patch.object(notifier.session, "post", return_value=fake_response()) as post:
            notifier.send(["第一則"])
        url, kwargs = post.call_args[0][0], post.call_args[1]
        self.assertIn("/bot111:AAA/sendMessage", url)
        self.assertEqual(kwargs["json"]["chat_id"], "123456789")
        self.assertEqual(kwargs["json"]["text"], "第一則")
        self.assertTrue(kwargs["json"]["link_preview_options"]["is_disabled"])

    def test_sends_every_message(self):
        notifier = TelegramNotifier(config())
        with mock.patch.object(notifier.session, "post", return_value=fake_response()) as post, \
             mock.patch("x_stock_tracker.notify.telegram.time.sleep"):
            notifier.send(["一", "二", "三"])
        self.assertEqual(post.call_count, 3)

    def test_rejects_username_as_private_chat_id(self):
        notifier = TelegramNotifier(config(chat_id="SCLU0215"))
        with self.assertRaises(NotifyError) as ctx:
            notifier.send(["x"])
        self.assertIn("TELEGRAM_CHAT_ID", str(ctx.exception))

    def test_accepts_negative_group_id_and_channel_name(self):
        for chat_id in ("-1001234567890", "@my_channel"):
            notifier = TelegramNotifier(config(chat_id=chat_id))
            with mock.patch.object(notifier.session, "post", return_value=fake_response()):
                notifier.send(["x"])  # 不應該拋錯

    def test_chat_not_found_gives_actionable_message(self):
        notifier = TelegramNotifier(config())
        resp = fake_response(400, {"ok": False, "description": "Bad Request: chat not found"})
        with mock.patch.object(notifier.session, "post", return_value=resp):
            with self.assertRaises(NotifyError) as ctx:
                notifier.send(["x"])
        self.assertIn("Start", str(ctx.exception))

    def test_invalid_token_reports_401(self):
        notifier = TelegramNotifier(config())
        resp = fake_response(401, {"ok": False, "description": "Unauthorized"})
        with mock.patch.object(notifier.session, "post", return_value=resp):
            with self.assertRaises(NotifyError) as ctx:
                notifier.send(["x"])
        self.assertIn("401", str(ctx.exception))

    def test_retries_on_rate_limit_then_succeeds(self):
        notifier = TelegramNotifier(config())
        limited = fake_response(429, {"ok": False, "description": "Too Many Requests",
                                      "parameters": {"retry_after": 1}})
        with mock.patch.object(notifier.session, "post", side_effect=[limited, fake_response()]) as post, \
             mock.patch("x_stock_tracker.notify.telegram.time.sleep"):
            notifier.send(["x"])
        self.assertEqual(post.call_count, 2)

    def test_verify_returns_bot_username(self):
        notifier = TelegramNotifier(config())
        resp = fake_response(200, {"ok": True, "result": {"username": "my_stock_bot"}})
        with mock.patch.object(notifier.session, "get", return_value=resp):
            self.assertEqual(notifier.verify(), "my_stock_bot")

    def test_verify_raises_on_bad_token(self):
        notifier = TelegramNotifier(config())
        resp = fake_response(401, {"ok": False, "description": "Unauthorized"})
        with mock.patch.object(notifier.session, "get", return_value=resp):
            with self.assertRaises(NotifyError):
                notifier.verify()


if __name__ == "__main__":
    unittest.main()
