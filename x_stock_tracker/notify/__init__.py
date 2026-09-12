"""推播管道。"""

from .base import Notifier, NotifyError
from .line import LineNotifier
from .stdout import StdoutNotifier


def build_notifier(config) -> Notifier:
    if config.notifier == "stdout":
        return StdoutNotifier()
    return LineNotifier(config)


__all__ = ["Notifier", "NotifyError", "LineNotifier", "StdoutNotifier", "build_notifier"]
