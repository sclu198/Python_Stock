"""透過 Telegram Bot API 推播訊息。

Telegram 沒有地區限制，設定也比 LINE 單純：跟 @BotFather 要一組 bot token，
再對自己的 bot 送一則訊息取得 chat id（見 scripts/telegram_get_chat_id.py）。

注意：bot 沒辦法用 @使用者名稱 主動私訊你，一定要用數字的 chat id，
而且你必須先對該 bot 按過 Start，否則 Telegram 會回 "chat not found"。
"""

from __future__ import annotations

import logging
import re
import time

import requests

from .base import Notifier, NotifyError

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
MAX_RETRIES = 4
# Telegram 單則訊息上限 4096 個 UTF-16 單位，留一點餘裕
MAX_MESSAGE_CHARS = 3900
CHAT_ID_RE = re.compile(r"^(-?\d+|@[A-Za-z0-9_]{5,})$")


class TelegramNotifier(Notifier):
    name = "telegram"
    max_message_chars = MAX_MESSAGE_CHARS

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    @property
    def _url(self) -> str:
        return f"{API_BASE}/bot{self.config.telegram_bot_token}/sendMessage"

    def verify(self) -> str:
        """呼叫 getMe 確認 token 可用，回傳 bot 的使用者名稱。"""
        url = f"{API_BASE}/bot{self.config.telegram_bot_token}/getMe"
        try:
            resp = self.session.get(url, timeout=self.config.http_timeout)
        except requests.RequestException as exc:
            raise NotifyError(f"連線 Telegram API 失敗：{exc}") from exc
        body = _json_or_empty(resp)
        if resp.status_code != 200 or not body.get("ok"):
            raise NotifyError(
                f"token 驗證失敗（{resp.status_code}）：{body.get('description', resp.text[:200])}"
            )
        return body.get("result", {}).get("username", "unknown")

    def send(self, messages: list[str]) -> None:
        if not messages:
            return
        chat_id = self.config.telegram_chat_id.strip()
        if not CHAT_ID_RE.match(chat_id):
            raise NotifyError(
                f"TELEGRAM_CHAT_ID 格式不對：{chat_id!r}。"
                "私訊請填數字 chat id（可執行 python scripts/telegram_get_chat_id.py 取得），"
                "頻道才可以用 @頻道名稱。"
            )
        for index, text in enumerate(messages):
            self._send_one(chat_id, text)
            if index < len(messages) - 1:
                time.sleep(1)  # 同一個對話 Telegram 限制約每秒一則

    def _send_one(self, chat_id: str, text: str) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "link_preview_options": {"is_disabled": True},
        }

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(self._url, json=payload, timeout=self.config.http_timeout)
            except requests.RequestException as exc:
                if attempt == MAX_RETRIES - 1:
                    raise NotifyError(f"連線 Telegram API 失敗：{exc}") from exc
                _sleep(attempt)
                continue

            if resp.status_code == 200:
                log.info("已推送 1 則訊息到 Telegram")
                return

            body = _json_or_empty(resp)
            description = body.get("description", resp.text[:300])

            if resp.status_code == 429:
                retry_after = int(body.get("parameters", {}).get("retry_after", 2 ** (attempt + 1)))
                if attempt == MAX_RETRIES - 1:
                    raise NotifyError(f"Telegram 回傳 429：{description}")
                log.warning("Telegram 限流，%d 秒後重試", retry_after)
                time.sleep(retry_after)
                continue
            if resp.status_code == 401:
                raise NotifyError("Telegram 回傳 401：bot token 無效，請跟 @BotFather 確認")
            if resp.status_code == 403:
                raise NotifyError(
                    f"Telegram 回傳 403：{description}。"
                    "通常是你把 bot 封鎖了，或還沒對它按過 Start。"
                )
            if resp.status_code == 400 and "chat not found" in description.lower():
                raise NotifyError(
                    "Telegram 回傳「chat not found」：chat id 不對，"
                    "或你還沒在 Telegram 對這個 bot 按過 Start。"
                )
            if resp.status_code >= 500:
                if attempt == MAX_RETRIES - 1:
                    raise NotifyError(f"Telegram 回傳 {resp.status_code}：{description}")
                _sleep(attempt)
                continue
            raise NotifyError(f"Telegram 回傳 {resp.status_code}：{description}")


def _json_or_empty(resp) -> dict:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _sleep(attempt: int) -> None:
    delay = 2 ** (attempt + 1)
    log.warning("Telegram 推播失敗，%d 秒後重試", delay)
    time.sleep(delay)
