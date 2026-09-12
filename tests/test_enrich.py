"""名錄校正邏輯的測試。"""

import unittest

from x_stock_tracker.analysis.enrich import enrich_mention
from x_stock_tracker.models import CompanyMention
from x_stock_tracker.tw_market.registry import TwCompanyRegistry, parse_rows

ROWS_LISTED = [
    {"公司代號": "2330", "公司名稱": "台灣積體電路製造股份有限公司", "公司簡稱": "台積電", "產業別": "24"}
]
ROWS_PUBLIC = [
    {"公司代號": "6919", "公司名稱": "世界先進測試股份有限公司", "公司簡稱": "世界測試", "產業別": "24"}
]


def registry():
    return TwCompanyRegistry(parse_rows(ROWS_LISTED, "listed") + parse_rows(ROWS_PUBLIC, "public"))


class TestEnrich(unittest.TestCase):
    def test_listed_company_gets_official_code_and_industry(self):
        mention = CompanyMention(
            company_name="台積電", market_country="台灣", ticker_guess="2303", industry_l1="科技"
        )
        result = enrich_mention(mention, registry())
        self.assertEqual(result.ticker, "2330")
        self.assertEqual(result.industry_l1, "半導體業")
        self.assertIn("上市", result.exchange)
        self.assertEqual(result.matched_source, "listed")

    def test_public_company_marked_unlisted_with_code(self):
        mention = CompanyMention(company_name="世界測試", market_country="台灣")
        result = enrich_mention(mention, registry())
        self.assertTrue(result.ticker.startswith("未上市"))
        self.assertIn("6919", result.ticker)

    def test_taiwanese_company_not_in_registry_is_unlisted(self):
        mention = CompanyMention(company_name="某某生技新創", market_country="台灣")
        result = enrich_mention(mention, registry())
        self.assertEqual(result.ticker, "未上市")
        self.assertIn("未上市", result.exchange)

    def test_foreign_company_keeps_model_ticker(self):
        mention = CompanyMention(
            company_name="NVIDIA",
            english_name="NVIDIA",
            market_country="美國",
            exchange="NASDAQ",
            ticker_guess="NVDA",
            ticker="NVDA",
        )
        result = enrich_mention(mention, registry())
        self.assertEqual(result.ticker, "NVDA")
        self.assertEqual(result.exchange, "NASDAQ")

    def test_foreign_company_english_name_does_not_match_tw_registry(self):
        mention = CompanyMention(
            company_name="World Test Inc.",
            english_name="World Test",
            market_country="美國",
            exchange="NASDAQ",
            ticker_guess="WTI",
            ticker="WTI",
        )
        result = enrich_mention(mention, registry())
        self.assertEqual(result.ticker, "WTI")
        self.assertEqual(result.matched_source, "")

    def test_unknown_market_still_matches_chinese_name(self):
        mention = CompanyMention(company_name="台灣積體電路製造", market_country="", exchange="未知")
        result = enrich_mention(mention, registry())
        self.assertEqual(result.ticker, "2330")


if __name__ == "__main__":
    unittest.main()
