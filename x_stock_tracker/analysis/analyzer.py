"""呼叫 Claude API 分析貼文，並用台股名錄校正結果。"""

from __future__ import annotations

import json
import logging

import anthropic

from ..models import CompanyMention, Post, PostAnalysis
from .enrich import enrich_all
from .schema import ANALYSIS_SCHEMA, SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)

WEB_SEARCH_TOOL_TYPE = "web_search_20260209"


class AnalysisError(RuntimeError):
    """模型分析失敗。"""


class PostAnalyzer:
    def __init__(self, config, registry=None):
        self.config = config
        self.registry = registry
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def analyze(self, post: Post) -> PostAnalysis:
        try:
            payload = self._call_model(post)
        except anthropic.APIError as exc:
            log.error("貼文 %s 分析失敗：%s", post.id, exc)
            return PostAnalysis(post=post, error=f"分析失敗：{exc}")
        except (AnalysisError, json.JSONDecodeError) as exc:
            log.error("貼文 %s 解析模型輸出失敗：%s", post.id, exc)
            return PostAnalysis(post=post, error=f"解析模型輸出失敗：{exc}")

        mentions = [_to_mention(item) for item in payload.get("companies", [])]
        if self.registry is not None:
            mentions = enrich_all(mentions, self.registry)

        return PostAnalysis(
            post=post,
            summary_bullets=[str(b).strip() for b in payload.get("summary_bullets", []) if str(b).strip()],
            companies=mentions,
            is_market_related=bool(payload.get("is_market_related", True)),
        )

    def analyze_all(self, posts: list[Post]) -> list[PostAnalysis]:
        return [self.analyze(post) for post in posts]

    def _call_model(self, post: Post) -> dict:
        kwargs = {
            "model": self.config.model,
            "max_tokens": 16000,
            "system": [
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": build_user_prompt(post)}],
            "output_config": {
                "effort": self.config.effort,
                "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA},
            },
        }
        if self.config.enable_web_search:
            kwargs["tools"] = [
                {
                    "type": WEB_SEARCH_TOOL_TYPE,
                    "name": "web_search",
                    "max_uses": self.config.web_search_max_uses,
                }
            ]

        with self.client.messages.stream(**kwargs) as stream:
            response = stream.get_final_message()

        if response.stop_reason == "refusal":
            detail = getattr(response.stop_details, "explanation", "") if response.stop_details else ""
            raise AnalysisError(f"模型拒絕回應：{detail}")

        return _extract_json(response)


def _extract_json(response) -> dict:
    """取出結構化輸出。搭配 web search 時 JSON 會在最後一個 text block。"""
    texts = [b.text for b in response.content if getattr(b, "type", "") == "text" and b.text.strip()]
    for text in reversed(texts):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise AnalysisError("回應中找不到合法的 JSON 結果")


def _to_mention(item: dict) -> CompanyMention:
    def get(key: str) -> str:
        return str(item.get(key, "") or "").strip()

    return CompanyMention(
        name_in_post=get("name_in_post"),
        company_name=get("company_name") or get("name_in_post"),
        english_name=get("english_name"),
        market_country=get("market_country"),
        exchange=get("exchange"),
        ticker_guess=get("ticker_guess"),
        ticker=get("ticker_guess") or "未上市",
        industry_l1=get("industry_l1"),
        industry_l2=get("industry_l2"),
        business_model_l3=get("business_model_l3"),
        impact_view=get("impact_view"),
        sentiment=get("sentiment") or "無法判斷",
        sentiment_reason=get("sentiment_reason"),
        confidence=get("confidence") or "中",
    )
