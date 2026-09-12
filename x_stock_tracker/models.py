"""資料結構定義。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class Post:
    """一則 X 貼文。"""

    id: str
    text: str
    created_at: datetime | None
    url: str
    author: str
    quoted_text: str = ""

    @property
    def full_text(self) -> str:
        if self.quoted_text:
            return f"{self.text}\n\n[引用的貼文內容]\n{self.quoted_text}"
        return self.text

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        return data


@dataclass
class CompanyMention:
    """貼文中提到的一家公司，以及對它的分析結果。"""

    name_in_post: str = ""
    company_name: str = ""
    english_name: str = ""
    market_country: str = ""
    exchange: str = ""
    ticker_guess: str = ""  # 模型給的代號，台股會被名錄覆寫
    ticker: str = "未上市"  # 最終顯示的代號
    industry_l1: str = ""
    industry_l2: str = ""
    business_model_l3: str = ""
    impact_view: str = ""
    sentiment: str = "無法判斷"
    sentiment_reason: str = ""
    confidence: str = "中"
    # 以下由台股名錄比對後補上
    matched_source: str = ""  # listed / otc / public / ""
    matched_name: str = ""

    @property
    def display_name(self) -> str:
        name = self.company_name or self.name_in_post
        if self.english_name and self.english_name.lower() not in name.lower():
            return f"{name}（{self.english_name}）"
        return name


@dataclass
class PostAnalysis:
    """一則貼文的完整分析。"""

    post: Post
    summary_bullets: list[str] = field(default_factory=list)
    companies: list[CompanyMention] = field(default_factory=list)
    is_market_related: bool = True
    error: str = ""


@dataclass
class TwCompany:
    """台股名錄中的一家公司。"""

    code: str
    name: str
    short_name: str
    english_name: str
    industry: str
    source: str  # listed(上市) / otc(上櫃) / public(公開發行、興櫃)

    MARKET_LABELS = {
        "listed": "台灣／上市（TWSE）",
        "otc": "台灣／上櫃（TPEx）",
        "public": "台灣／公開發行或興櫃（未上市櫃）",
    }

    @property
    def market_label(self) -> str:
        return self.MARKET_LABELS.get(self.source, "台灣")

    @property
    def is_exchange_listed(self) -> bool:
        return self.source in {"listed", "otc"}
