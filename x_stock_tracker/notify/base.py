"""推播介面。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class NotifyError(RuntimeError):
    """推播失敗。"""


class Notifier(ABC):
    name = "base"
    # 各家平台的單則訊息長度上限（以 UTF-16 單位計算，表情符號算兩個）
    max_message_chars = 3900

    @abstractmethod
    def send(self, messages: list[str]) -> None:
        raise NotImplementedError
