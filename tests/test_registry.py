"""台股名錄解析與查詢的測試（不連網，用固定樣本）。"""

import unittest

from x_stock_tracker.tw_market.industry_codes import industry_label
from x_stock_tracker.tw_market.registry import (
    TwCompanyRegistry,
    normalize_name,
    parse_rows,
)

# TWSE 風格：中文欄位名、產業別是數字代號
TWSE_ROWS = [
    {
        "出表日期": "1150912",
        "公司代號": "2330",
        "公司名稱": "台灣積體電路製造股份有限公司",
        "公司簡稱": "台積電",
        "產業別": "24",
        "英文簡稱": "TSMC",
    },
    {
        "出表日期": "1150912",
        "公司代號": "2454",
        "公司名稱": "聯發科技股份有限公司",
        "公司簡稱": "聯發科",
        "產業別": "24",
        "英文簡稱": "MEDIATEK",
    },
]

# TPEx 風格：英文欄位名、產業別是中文
TPEX_ROWS = [
    {
        "SecuritiesCompanyCode": "6488",
        "CompanyName": "環球晶圓股份有限公司",
        "CompanyAbbreviation": "環球晶",
        "IndustryName": "半導體業",
        "EnglishName": "GlobalWafers",
    }
]

PUBLIC_ROWS = [
    {
        "公司代號": "6919",
        "公司名稱": "世界先進測試股份有限公司",
        "公司簡稱": "世界測試",
        "產業別": "24",
    }
]


class TestParsing(unittest.TestCase):
    def test_parses_chinese_keys(self):
        companies = parse_rows(TWSE_ROWS, "listed")
        self.assertEqual(len(companies), 2)
        self.assertEqual(companies[0].code, "2330")
        self.assertEqual(companies[0].short_name, "台積電")
        self.assertEqual(companies[0].industry, "半導體業")

    def test_parses_english_keys(self):
        companies = parse_rows(TPEX_ROWS, "otc")
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0].code, "6488")
        self.assertEqual(companies[0].short_name, "環球晶")
        self.assertEqual(companies[0].industry, "半導體業")

    def test_skips_rows_without_code_or_name(self):
        self.assertEqual(parse_rows([{"備註": "空的"}, "壞資料"], "listed"), [])

    def test_falls_back_to_value_shape_when_keys_unknown(self):
        rows = [{"代號欄": "1101", "名稱欄位": "台灣水泥股份有限公司"}]
        companies = parse_rows(rows, "listed")
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0].code, "1101")

    def test_industry_label_keeps_unknown_values(self):
        self.assertEqual(industry_label("24"), "半導體業")
        self.assertEqual(industry_label("半導體業"), "半導體業")
        self.assertEqual(industry_label(""), "")


class TestNormalize(unittest.TestCase):
    def test_strips_company_suffix_and_unifies_tai(self):
        self.assertEqual(
            normalize_name("臺灣積體電路製造股份有限公司"), normalize_name("台灣積體電路製造")
        )

    def test_ignores_spaces_and_punctuation(self):
        self.assertEqual(normalize_name("聯發科 技"), normalize_name("聯發科技"))


class TestLookup(unittest.TestCase):
    def setUp(self):
        self.registry = TwCompanyRegistry(
            parse_rows(TWSE_ROWS, "listed")
            + parse_rows(TPEX_ROWS, "otc")
            + parse_rows(PUBLIC_ROWS, "public")
        )

    def test_lookup_by_short_name(self):
        self.assertEqual(self.registry.lookup("台積電").code, "2330")

    def test_lookup_by_full_name_with_suffix(self):
        self.assertEqual(self.registry.lookup("台灣積體電路製造股份有限公司").code, "2330")

    def test_lookup_by_code(self):
        self.assertEqual(self.registry.lookup("2454").short_name, "聯發科")

    def test_lookup_by_english_name(self):
        self.assertEqual(self.registry.lookup("TSMC").code, "2330")

    def test_lookup_otc_and_public_sources(self):
        self.assertEqual(self.registry.lookup("環球晶").source, "otc")
        self.assertEqual(self.registry.lookup("世界測試").source, "public")

    def test_unknown_company_returns_none(self):
        self.assertIsNone(self.registry.lookup("某某未上市新創"))

    def test_short_input_does_not_fuzzy_match(self):
        self.assertIsNone(self.registry.lookup("A"))

    def test_multiple_candidates_uses_first_hit(self):
        self.assertEqual(self.registry.lookup("", "不存在的公司", "聯發科").code, "2454")

    def test_counts(self):
        self.assertEqual(self.registry.counts(), {"listed": 2, "otc": 1, "public": 1})


if __name__ == "__main__":
    unittest.main()
