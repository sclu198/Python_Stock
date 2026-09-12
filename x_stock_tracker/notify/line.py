"""透過 LINE Messaging API 推播訊息。

注意：LINE 的 push API 只認 U 開頭的 userId，不能用 LINE ID（例如 brucelu215）。
取得自己的 userId 的方法見 docs/SETUP.md 與 scripts/line_get_user_id.py。
"""

from __future__ import annotations

import logging
import time
import uuid

import requests

from .base import Notifier, NotifyError

log = logging.getLogger(__name__)

PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_MESSAGES_PER_REQUEST = 5
MAX_RETRIES = 4


class LineNotifier(Notifier):
    name = "line"

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.line_channel_access_token}",
                "Content-Type": "application/json",
            }
        )

    def send(self, messages: list[str]) -> None:
        if not messages:
            return
        to = self.config.line_to_user_id
        if not to.startswith("U"):
            raise NotifyError(
                f"LINE_TO_USER_ID 看起來不是 userId：{to!r}。"
                "需要 U 開頭的 33 字元 userId，不是 LINE ID。"
            )
        for start in range(0, len(messages), MAX_MESSAGES_PER_REQUEST):
            batch = messages[start : start + MAX_MESSAGES_PER_REQUEST]
            self._push(to, batch)

    def _push(self, to: str, batch: list[str]) -> None:
        body = {"to": to, "messages": [{"type": "text", "text": text} for text in batch]}
        headers = {"X-Line-Retry-Key": str(uuid.uuid4())}

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(
                    PUSH_URL, json=body, headers=headers, timeout=self.config.http_timeout
                )
            except requests.RequestException as exc:
                if attempt == MAX_RETRIES - 1:
                    raise NotifyError(f"連線 LINE API 失敗：{exc}") from exc
                _sleep(attempt)
                continue

            if resp.status_code == 200:
                log.info("已推送 %d 則訊息到 LINE", len(batch))
                return
            if resp.status_code == 401:
                raise NotifyError("LINE 回傳 401：channel access token 無效或過期")
            if resp.status_code == 403:
                raise NotifyError(
                    "LINE 回傳 403：沒有推播權限。請確認該帳號已加入這個 Messaging API bot 為好友，"
                    "且 userId 屬於同一個 channel。"
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == MAX_RETRIES - 1:
                    raise NotifyError(f"LINE 回傳 {resp.status_code}：{resp.text[:300]}")
                _sleep(attempt)
                continue
            raise NotifyError(f"LINE 回傳 {resp.status_code}：{resp.text[:300]}")


def _sleep(attempt: int) -> None:
    delay = 2 ** (attempt + 1)
    log.warning("LINE 推播失敗，%d 秒後重試", delay)
    time.sleep(delay)
