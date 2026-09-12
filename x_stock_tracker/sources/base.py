"""貼文來源的共用介面。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Post


class SourceError(RuntimeError):
    """抓取貼文失敗。"""


class PostSource(ABC):
    name = "base"

    @abstractmethod
    def fetch(self, since_id: str = "") -> list[Post]:
        """回傳由舊到新排序的貼文。"""
        raise NotImplementedError
