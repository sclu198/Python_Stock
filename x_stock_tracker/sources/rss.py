"""用 RSS 來源抓貼文（RSSHub / Nitter 之類的鏡像服務）。

當 X API 方案不支援讀取推文時的備援；X_SOURCE=rss 且 X_RSS_URL 指向
例如 https://rsshub.example.com/twitter/user/qq_timmy 即可。
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

from ..models import Post
from .base import PostSource, SourceError

log = logging.getLogger(__name__)

STATUS_ID_RE = re.compile(r"/status(?:es)?/(\d+)")
TAG_RE = re.compile(r"<[^>]+>")


class RssSource(PostSource):
    name = "rss"

    def __init__(self, config, state=None):
        self.config = config
        self.state = state

    def fetch(self, since_id: str = "") -> list[Post]:
        try:
            resp = requests.get(
                self.config.x_rss_url,
                timeout=self.config.http_timeout,
                headers={"User-Agent": "x-stock-tracker/0.1"},
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise SourceError(f"讀取 RSS 失敗：{exc}") from exc

        try:
            root = ElementTree.fromstring(resp.content)
        except ElementTree.ParseError as exc:
            raise SourceError(f"RSS 格式解析失敗：{exc}") from exc

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.lookback_hours)
        posts: list[Post] = []
        for item in root.iter("item"):
            post = self._to_post(item)
            if post is None:
                continue
            if since_id and post.id.isdigit() and since_id.isdigit():
                if int(post.id) <= int(since_id):
                    continue
            elif post.created_at and post.created_at < cutoff:
                continue
            posts.append(post)

        posts.sort(key=lambda p: (p.created_at or datetime.min.replace(tzinfo=timezone.utc)))
        log.info("RSS 取得 %d 則貼文", len(posts))
        return posts[-self.config.max_posts_per_run :]

    def _to_post(self, item) -> Post | None:
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        match = STATUS_ID_RE.search(link) or STATUS_ID_RE.search(guid)
        post_id = match.group(1) if match else (guid or link)
        if not post_id:
            return None

        body = item.findtext("description") or item.findtext("title") or ""
        return Post(
            id=post_id,
            text=_strip_html(body),
            created_at=_parse_rfc822(item.findtext("pubDate") or ""),
            url=link or f"https://x.com/{self.config.x_username}/status/{post_id}",
            author=self.config.x_username,
        )


def _strip_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _parse_rfc822(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
