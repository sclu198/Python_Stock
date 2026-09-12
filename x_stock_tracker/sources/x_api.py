"""用 X API v2 抓取指定帳號的貼文。

需要 X API 的 App-only Bearer Token，且方案必須含有讀取推文的權限
（免費方案不能讀推文，詳見 docs/SETUP.md）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from ..models import Post
from .base import PostSource, SourceError

log = logging.getLogger(__name__)

API_BASE = "https://api.twitter.com/2"
TWEET_FIELDS = "created_at,text,note_tweet,referenced_tweets,lang,public_metrics"


class XApiSource(PostSource):
    name = "x_api"

    def __init__(self, config, state=None):
        self.config = config
        self.state = state
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.x_bearer_token}",
                "User-Agent": "x-stock-tracker/0.1",
            }
        )

    def _get(self, url: str, params: dict) -> dict:
        try:
            resp = self.session.get(url, params=params, timeout=self.config.http_timeout)
        except requests.RequestException as exc:
            raise SourceError(f"連線 X API 失敗：{exc}") from exc

        if resp.status_code == 429:
            reset = resp.headers.get("x-rate-limit-reset", "")
            detail = f"，額度於 unix time {reset} 之後重置" if reset else ""
            raise SourceError(f"X API 回傳 429（超出流量限制）{detail}")
        if resp.status_code == 401:
            raise SourceError("X API 回傳 401：Bearer Token 無效或過期")
        if resp.status_code == 403:
            raise SourceError(
                "X API 回傳 403：目前的 API 方案沒有讀取推文的權限"
                "（免費方案無法讀取，需要 Basic 以上，或改用 X_SOURCE=rss）"
            )
        if resp.status_code >= 400:
            raise SourceError(f"X API 回傳 {resp.status_code}：{resp.text[:300]}")
        return resp.json()

    def resolve_user_id(self) -> str:
        cached = self.state.user_id if self.state else ""
        if cached:
            return cached
        data = self._get(
            f"{API_BASE}/users/by/username/{self.config.x_username}", {"user.fields": "id"}
        )
        user_id = (data.get("data") or {}).get("id", "")
        if not user_id:
            raise SourceError(f"找不到帳號 @{self.config.x_username}")
        if self.state:
            self.state.user_id = user_id
        return user_id

    def fetch(self, since_id: str = "") -> list[Post]:
        user_id = self.resolve_user_id()
        params = {
            "max_results": max(5, min(100, self.config.max_posts_per_run)),
            "exclude": "retweets,replies",
            "tweet.fields": TWEET_FIELDS,
            "expansions": "referenced_tweets.id",
        }
        if since_id:
            params["since_id"] = since_id
        else:
            start = datetime.now(timezone.utc) - timedelta(hours=self.config.lookback_hours)
            params["start_time"] = start.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = self._get(f"{API_BASE}/users/{user_id}/tweets", params)
        tweets = data.get("data") or []
        includes = {t["id"]: t for t in (data.get("includes", {}).get("tweets") or [])}

        posts = [self._to_post(t, includes) for t in tweets]
        posts.sort(key=lambda p: (p.created_at or datetime.min.replace(tzinfo=timezone.utc)))
        log.info("X API 取得 %d 則貼文", len(posts))
        return posts

    def _to_post(self, tweet: dict, includes: dict) -> Post:
        text = (tweet.get("note_tweet") or {}).get("text") or tweet.get("text", "")
        quoted = ""
        for ref in tweet.get("referenced_tweets") or []:
            if ref.get("type") in {"quoted", "replied_to"}:
                src = includes.get(ref.get("id", ""))
                if src:
                    quoted = (src.get("note_tweet") or {}).get("text") or src.get("text", "")
                break
        return Post(
            id=str(tweet.get("id", "")),
            text=text,
            created_at=_parse_time(tweet.get("created_at", "")),
            url=f"https://x.com/{self.config.x_username}/status/{tweet.get('id', '')}",
            author=self.config.x_username,
            quoted_text=quoted,
        )


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
