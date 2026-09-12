"""把訊息印到終端機，方便本機測試。"""

from __future__ import annotations

from .base import Notifier


class StdoutNotifier(Notifier):
    name = "stdout"
    max_message_chars = 3900

    def send(self, messages: list[str]) -> None:
        for index, message in enumerate(messages, 1):
            print(f"\n===== 訊息 {index}/{len(messages)}（{len(message)} 字）=====")
            print(message)
