"""用台股名錄校正 LLM 給的公司資訊。

模型可能記錯股票代號，所以台股一律以證交所／櫃買中心的開放資料為準；
查不到的就照使用者要求標示「未上市」。
"""

from __future__ import annotations

import re

from ..models import CompanyMention

CJK_RE = re.compile(r"[一-鿿]")
TW_CODE_RE = re.compile(r"^[0-9]{4,6}[A-Z]?$")
TW_MARKET_HINTS = ("台灣", "臺灣", "taiwan", "twse", "tpex", "櫃買", "證交所", "興櫃")
TW_MARKET_TOKENS = {"tw", "twn"}  # 整個詞才算，避免撞到其他字串
NON_TW_HINTS = ("美國", "日本", "南韓", "韓國", "中國", "香港", "歐洲", "荷蘭", "德國", "新加坡")

UNLISTED = "未上市"


def looks_taiwanese(mention: CompanyMention) -> bool:
    haystack = f"{mention.market_country} {mention.exchange}".casefold()
    if any(hint in haystack for hint in TW_MARKET_HINTS):
        return True
    return bool(TW_MARKET_TOKENS & set(re.split(r"[^a-z0-9]+", haystack)))


def looks_foreign(mention: CompanyMention) -> bool:
    haystack = f"{mention.market_country} {mention.exchange}"
    return any(hint in haystack for hint in NON_TW_HINTS) and not looks_taiwanese(mention)


def enrich_mention(mention: CompanyMention, registry) -> CompanyMention:
    """比對台股名錄，補上／修正股票代號、市場與第一層產業。"""
    candidates = [mention.company_name, mention.name_in_post, mention.english_name]
    guess = (mention.ticker_guess or "").strip()
    if TW_CODE_RE.match(guess):
        candidates.insert(0, guess)

    if looks_foreign(mention):
        # 模型判定是外國公司時，只用中文名比對，避免英文簡稱誤撞台股
        candidates = [c for c in candidates if c and CJK_RE.search(c)]

    hit = registry.lookup(*candidates) if (registry and candidates) else None

    if hit is None:
        if looks_taiwanese(mention):
            mention.ticker = UNLISTED
            mention.exchange = "台灣／未在上市、上櫃及公開發行名錄中（未上市）"
        elif not mention.ticker or mention.ticker == UNLISTED:
            mention.ticker = mention.ticker_guess or UNLISTED
        return mention

    mention.matched_source = hit.source
    mention.matched_name = hit.name
    mention.market_country = "台灣"
    mention.exchange = hit.market_label
    if hit.is_exchange_listed:
        mention.ticker = hit.code
    else:
        mention.ticker = f"{UNLISTED}（公開發行／興櫃，代號 {hit.code}）"
    if hit.industry:
        mention.industry_l1 = hit.industry
    if hit.short_name and hit.short_name not in mention.company_name:
        mention.company_name = mention.company_name or hit.short_name
    return mention


def enrich_all(mentions: list[CompanyMention], registry) -> list[CompanyMention]:
    return [enrich_mention(m, registry) for m in mentions]
