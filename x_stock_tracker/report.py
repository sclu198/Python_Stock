"""把分析結果排版成 LINE 訊息。

LINE 純文字訊息不支援 Markdown，所以用符號與縮排做層次；
單則訊息上限 5000 字，這裡以貼文為單位切塊再組裝。
"""

from __future__ import annotations

from datetime import datetime

from .models import PostAnalysis

MAX_MESSAGE_CHARS = 4800
DIVIDER = "──────────────"

SENTIMENT_ICONS = {
    "利多": "🔺 利多",
    "偏多": "🔼 偏多",
    "利空": "🔻 利空",
    "偏空": "🔽 偏空",
    "中性": "➖ 中性",
    "無法判斷": "❔ 無法判斷",
}


def build_blocks(analyses: list[PostAnalysis], username: str, now: datetime) -> list[str]:
    """回傳一串文字區塊：第 0 塊是總覽，之後每則貼文一塊。"""
    post_blocks = [_format_post(a, idx + 1, len(analyses)) for idx, a in enumerate(analyses)]
    header = _format_header(analyses, username, now)
    return [header, *post_blocks]


def build_messages(analyses: list[PostAnalysis], username: str, now: datetime) -> list[str]:
    """把區塊組裝成數則 LINE 訊息，每則不超過長度上限。"""
    blocks = build_blocks(analyses, username, now)
    messages: list[str] = []
    current = ""
    for block in blocks:
        for piece in _split_oversized(block):
            if not current:
                current = piece
            elif len(current) + len(piece) + 2 <= MAX_MESSAGE_CHARS:
                current = f"{current}\n\n{piece}"
            else:
                messages.append(current)
                current = piece
    if current:
        messages.append(current)
    return messages


def build_empty_message(username: str, now: datetime) -> str:
    return (
        f"📊 X 貼文投資摘要\n"
        f"👤 @{username}｜{now.strftime('%Y-%m-%d %H:%M')}\n"
        f"{DIVIDER}\n"
        f"這段期間沒有新貼文。"
    )


def _format_header(analyses: list[PostAnalysis], username: str, now: datetime) -> str:
    company_names = []
    for analysis in analyses:
        for company in analysis.companies:
            label = company.display_name
            if label and label not in company_names:
                company_names.append(label)
    lines = [
        "📊 X 貼文投資摘要",
        f"👤 @{username}｜{now.strftime('%Y-%m-%d %H:%M')}",
        f"📝 {len(analyses)} 則貼文、{len(company_names)} 家公司",
    ]
    if company_names:
        lines.append("🏷 " + "、".join(company_names[:12]) + ("…" if len(company_names) > 12 else ""))
    return "\n".join(lines)


def _format_post(analysis: PostAnalysis, index: int, total: int) -> str:
    post = analysis.post
    when = post.created_at.astimezone().strftime("%m/%d %H:%M") if post.created_at else "時間未知"
    lines = [DIVIDER, f"【貼文 {index}/{total}】{when}", f"🔗 {post.url}"]

    if analysis.error:
        lines += ["", f"⚠️ {analysis.error}", "", "原文：", _clip(post.text, 400)]
        return "\n".join(lines)

    lines.append("")
    lines.append("📝 內容摘要")
    if analysis.summary_bullets:
        lines += [f"  ・{bullet}" for bullet in analysis.summary_bullets]
    else:
        lines.append(f"  ・{_clip(post.text, 200)}")

    if not analysis.companies:
        lines.append("")
        lines.append("🏢 未提到具體公司" + ("（非市場相關貼文）" if not analysis.is_market_related else ""))
        return "\n".join(lines)

    for company in analysis.companies:
        lines.append("")
        lines += _format_company(company)
    return "\n".join(lines)


def _format_company(company) -> list[str]:
    market = _market_label(company)
    sentiment = SENTIMENT_ICONS.get(company.sentiment, f"❔ {company.sentiment}")
    industry = " ＞ ".join(
        part for part in (company.industry_l1, company.industry_l2) if part
    ) or "產業未分類"

    lines = [
        f"🏢 {company.display_name}",
        f"  📍 市場：{market}",
        f"  🔢 代號：{company.ticker or '未上市'}",
        f"  🏭 產業：{industry}",
    ]
    if company.business_model_l3:
        lines.append(f"  🔧 商業模式／供應鏈角色：{company.business_model_l3}")
    if company.impact_view:
        lines.append(f"  📈 影響與市場看法：{company.impact_view}")
    reason = f"｜{company.sentiment_reason}" if company.sentiment_reason else ""
    lines.append(f"  💡 投資影響：{sentiment}{reason}")
    if company.confidence == "低":
        lines.append("  ⚠️ 判斷把握度低，請自行查證")
    return lines


def _market_label(company) -> str:
    """組出「國家／交易所」；台股名錄已經給過完整標籤就直接用。"""
    country = (company.market_country or "").strip()
    exchange = (company.exchange or "").strip()
    if not exchange:
        return country or "市場未知"
    if not country or country in exchange:
        return exchange
    return f"{country}／{exchange}"


def _split_oversized(block: str) -> list[str]:
    """單一區塊超過長度上限時，依行切成多段。"""
    if len(block) <= MAX_MESSAGE_CHARS:
        return [block]
    pieces: list[str] = []
    current = ""
    for line in block.split("\n"):
        line = line if len(line) <= MAX_MESSAGE_CHARS else line[: MAX_MESSAGE_CHARS - 1] + "…"
        if not current:
            current = line
        elif len(current) + len(line) + 1 <= MAX_MESSAGE_CHARS:
            current = f"{current}\n{line}"
        else:
            pieces.append(current)
            current = line
    if current:
        pieces.append(current)
    return pieces


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
