"""訊息排版的測試。"""

import unittest
from datetime import datetime, timezone

from x_stock_tracker.models import CompanyMention, Post, PostAnalysis
from x_stock_tracker.report import (
    MAX_MESSAGE_CHARS,
    build_empty_message,
    build_messages,
)

NOW = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)


def make_analysis(text="台積電 CoWoS 產能再開", companies=None, error=""):
    post = Post(
        id="1",
        text=text,
        created_at=NOW,
        url="https://x.com/qq_timmy/status/1",
        author="qq_timmy",
    )
    return PostAnalysis(
        post=post,
        summary_bullets=["CoWoS 產能持續擴張", "客戶追加訂單"],
        companies=companies if companies is not None else [],
        error=error,
    )


TSMC = CompanyMention(
    name_in_post="台積電",
    company_name="台積電",
    english_name="TSMC",
    market_country="台灣",
    exchange="台灣／上市（TWSE）",
    ticker="2330",
    industry_l1="半導體業",
    industry_l2="晶圓代工",
    business_model_l3="替 IC 設計公司代工先進製程晶圓，按晶圓片數收費",
    impact_view="市場解讀為 AI 需求延續",
    sentiment="利多",
    sentiment_reason="產能擴張代表訂單能見度高",
    confidence="高",
)


class TestReport(unittest.TestCase):
    def test_message_contains_all_six_sections(self):
        messages = build_messages([make_analysis(companies=[TSMC])], "qq_timmy", NOW)
        body = "\n".join(messages)
        self.assertIn("台積電", body)          # 1. 公司名
        self.assertIn("上市（TWSE）", body)     # 1. 所屬市場
        self.assertIn("2330", body)            # 2. 股票代號
        self.assertIn("半導體業 ＞ 晶圓代工", body)  # 3. 產業第一、二層
        self.assertIn("按晶圓片數收費", body)    # 3. 第三層商業模式
        self.assertIn("CoWoS 產能持續擴張", body)  # 4. 條列摘要
        self.assertIn("市場解讀為 AI 需求延續", body)  # 5. 影響與市場看法
        self.assertIn("利多", body)             # 6. 利多／利空

    def test_post_without_company(self):
        body = "\n".join(build_messages([make_analysis()], "qq_timmy", NOW))
        self.assertIn("未提到具體公司", body)

    def test_failed_analysis_shows_error_and_original_text(self):
        body = "\n".join(build_messages([make_analysis(error="分析失敗：逾時")], "qq_timmy", NOW))
        self.assertIn("分析失敗：逾時", body)
        self.assertIn("台積電 CoWoS", body)

    def test_low_confidence_is_flagged(self):
        low = CompanyMention(company_name="某公司", ticker="未上市", confidence="低")
        body = "\n".join(build_messages([make_analysis(companies=[low])], "qq_timmy", NOW))
        self.assertIn("把握度低", body)

    def test_messages_respect_length_limit(self):
        many = [make_analysis(companies=[TSMC]) for _ in range(40)]
        messages = build_messages(many, "qq_timmy", NOW)
        self.assertGreater(len(messages), 1)
        for message in messages:
            self.assertLessEqual(len(message), MAX_MESSAGE_CHARS)

    def test_single_huge_post_is_split(self):
        giant = CompanyMention(company_name="巨型公司", business_model_l3="很長。" * 4000)
        messages = build_messages([make_analysis(companies=[giant])], "qq_timmy", NOW)
        for message in messages:
            self.assertLessEqual(len(message), MAX_MESSAGE_CHARS)

    def test_header_counts_posts_and_companies(self):
        messages = build_messages(
            [make_analysis(companies=[TSMC]), make_analysis(companies=[TSMC])], "qq_timmy", NOW
        )
        self.assertIn("2 則貼文、1 家公司", messages[0])

    def test_empty_message(self):
        self.assertIn("沒有新貼文", build_empty_message("qq_timmy", NOW))


if __name__ == "__main__":
    unittest.main()
