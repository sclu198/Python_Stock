"""推播管道。"""

from .base import Notifier, NotifyError
from .line import LineNotifier
from .stdout import StdoutNotifier
from .telegram import TelegramNotifier

NOTIFIERS = {
    "telegram": TelegramNotifier,
    "line": LineNotifier,
    "stdout": StdoutNotifier,
}


def build_notifier(config) -> Notifier:
    if config.notifier == "stdout":
        return StdoutNotifier()
    cls = NOTIFIERS.get(config.notifier)
    if cls is None:
        raise NotifyError(f"不認得的 NOTIFIER 設定：{config.notifier!r}，可用：{', '.join(NOTIFIERS)}")
    return cls(config)


__all__ = [
    "Notifier",
    "NotifyError",
    "TelegramNotifier",
    "LineNotifier",
    "StdoutNotifier",
    "build_notifier",
]
