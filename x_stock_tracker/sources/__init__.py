"""貼文來源。"""

from .base import PostSource, SourceError
from .rss import RssSource
from .x_api import XApiSource


def build_source(config, state=None) -> PostSource:
    """依設定選擇資料來源：X API 或 RSS 鏡像。"""
    if config.x_source == "rss":
        return RssSource(config, state)
    return XApiSource(config, state)


__all__ = ["PostSource", "SourceError", "XApiSource", "RssSource", "build_source"]
