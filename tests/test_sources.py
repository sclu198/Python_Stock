"""貼文來源解析的測試（不連網）。"""

import unittest
from datetime import datetime, timezone
from unittest import mock
from xml.etree import ElementTree

from x_stock_tracker.config import Config
from x_stock_tracker.sources.rss import RssSource
from x_stock_tracker.sources.x_api import XApiSource

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>qq_timmy</title>
    <description>&lt;p&gt;台積電法說會&lt;br/&gt;展望樂觀&lt;/p&gt;</description>
    <link>https://x.com/qq_timmy/status/1800000000000000001</link>
    <pubDate>Fri, 12 Sep 2026 01:00:00 GMT</pubDate>
  </item>
  <item>
    <title>qq_timmy</title>
    <description>純文字貼文</description>
    <link>https://x.com/qq_timmy/status/1800000000000000002</link>
    <pubDate>Fri, 12 Sep 2026 02:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


def config():
    return Config(x_username="qq_timmy", x_source="rss", x_rss_url="https://example.test/feed")


class TestRssSource(unittest.TestCase):
    def test_parses_items(self):
        source = RssSource(config())
        items = list(ElementTree.fromstring(RSS_SAMPLE).iter("item"))
        post = source._to_post(items[0])
        self.assertEqual(post.id, "1800000000000000001")
        self.assertEqual(post.text, "台積電法說會\n展望樂觀")
        self.assertEqual(post.created_at, datetime(2026, 9, 12, 1, 0, tzinfo=timezone.utc))

    def test_fetch_filters_by_since_id_and_sorts(self):
        source = RssSource(config())
        response = mock.Mock(content=RSS_SAMPLE.encode("utf-8"))
        response.raise_for_status = mock.Mock()
        with mock.patch("x_stock_tracker.sources.rss.requests.get", return_value=response):
            posts = source.fetch(since_id="1800000000000000001")
        self.assertEqual([p.id for p in posts], ["1800000000000000002"])


class TestXApiSource(unittest.TestCase):
    def test_uses_note_tweet_text_when_present(self):
        source = XApiSource(Config(x_username="qq_timmy", x_bearer_token="t"))
        post = source._to_post(
            {
                "id": "123",
                "text": "被截斷的短版…",
                "note_tweet": {"text": "完整的長貼文內容"},
                "created_at": "2026-09-12T01:00:00.000Z",
            },
            {},
        )
        self.assertEqual(post.text, "完整的長貼文內容")
        self.assertEqual(post.url, "https://x.com/qq_timmy/status/123")

    def test_includes_quoted_tweet_text(self):
        source = XApiSource(Config(x_username="qq_timmy", x_bearer_token="t"))
        post = source._to_post(
            {
                "id": "123",
                "text": "同意",
                "referenced_tweets": [{"type": "quoted", "id": "999"}],
                "created_at": "2026-09-12T01:00:00.000Z",
            },
            {"999": {"text": "原始論點"}},
        )
        self.assertIn("原始論點", post.full_text)


if __name__ == "__main__":
    unittest.main()
