"""推播介面。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class NotifyError(RuntimeError):
    """推播失敗。"""


class Notifier(ABC):
    name = "base"

    @abstractmethod
    def send(self, messages: list[str]) -> None:
        raise NotImplementedError
