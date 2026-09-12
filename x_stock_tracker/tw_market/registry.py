"""台股公司名錄：抓取 TWSE／TPEx 開放資料，提供「公司名 -> 股票代號」查詢。

資料來源（由使用者指定）：
  上市      https://openapi.twse.com.tw/v1/opendata/t187ap03_L
  上櫃      https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O
  公開發行  https://openapi.twse.com.tw/v1/opendata/t187ap03_P

三個來源的欄位命名不一致（TWSE 用中文鍵、TPEx 曾用英文鍵），所以這裡用
「候選鍵名 + 值的形態推斷」來對應欄位，任一邊改欄位名都不會直接壞掉。
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import requests

from ..models import TwCompany
from .industry_codes import industry_label

log = logging.getLogger(__name__)

CODE_KEYS = ("公司代號", "股票代號", "證券代號", "SecuritiesCompanyCode", "CompanyCode", "Code")
NAME_KEYS = ("公司名稱", "CompanyName", "Name")
SHORT_KEYS = ("公司簡稱", "CompanyAbbreviation", "SecuritiesCompanyAbbreviation", "Abbreviation", "簡稱")
ENGLISH_KEYS = ("英文簡稱", "英文全稱", "CompanyEnglishName", "EnglishAbbreviation", "EnglishName")
INDUSTRY_KEYS = ("產業別", "IndustryName", "SecuritiesIndustryName", "SecuritiesIndustryCode", "Industry")

# 欄位名稱不在上面清單時，改用關鍵字推斷；exclude 用來擋掉會誤抓的欄位
CODE_HINTS = (("代號", "代碼", "code"), ("統一編號", "營利事業", "uniform", "tax"))
NAME_HINTS = (("名稱", "name"), ("英文", "english", "簡稱", "abbrev", "short"))
SHORT_HINTS = (("簡稱", "abbrev", "short"), ("英文", "english"))
ENGLISH_HINTS = (("英文", "english"), ())
INDUSTRY_HINTS = (("產業", "industry"), ())

CODE_RE = re.compile(r"^[0-9]{4,6}[A-Z]?$")
COMPANY_SUFFIXES = ("股份有限公司", "有限公司", "股份公司", "公司")
SOURCE_PRIORITY = {"listed": 0, "otc": 1, "public": 2}


class RegistryError(RuntimeError):
    """名錄下載或解析失敗。"""


def normalize_name(raw: str) -> str:
    """公司名稱正規化，讓「台積電」「臺積電」「台灣積體電路製造股份有限公司」可以互相比對。"""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw).strip()
    text = text.replace("臺", "台")
    for suffix in COMPANY_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
            break
    text = re.sub(r"[\s　().．,，、\-—_*·・'\"]", "", text)
    return text.casefold()


def _pick(
    row: dict[str, Any],
    keys: Iterable[str],
    hints: tuple[tuple[str, ...], tuple[str, ...]] | None = None,
) -> str:
    """先用確定的欄位名，再用關鍵字推斷，讓欄位改名時不會整個壞掉。"""
    stripped = {k.strip(): k for k in row}
    for key in keys:
        actual = stripped.get(key)
        if actual is not None and str(row[actual]).strip():
            return str(row[actual]).strip()

    if not hints:
        return ""
    wanted, excluded = hints
    for actual in row:
        lowered = actual.strip().casefold()
        if any(bad.casefold() in lowered for bad in excluded):
            continue
        if any(good.casefold() in lowered for good in wanted) and str(row[actual]).strip():
            return str(row[actual]).strip()
    return ""


def _guess_code(row: dict[str, Any]) -> str:
    """欄位名全部對不上時，找出看起來像股票代號的欄位值。"""
    for key, value in row.items():
        text = str(value).strip()
        if CODE_RE.match(text) and ("代號" in key or "code" in key.casefold()):
            return text
    for value in row.values():
        text = str(value).strip()
        if CODE_RE.match(text) and len(text) == 4:
            return text
    return ""


def parse_rows(rows: list[dict[str, Any]], source: str) -> list[TwCompany]:
    """把開放資料的原始列轉成 TwCompany。"""
    companies: list[TwCompany] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _pick(row, CODE_KEYS, CODE_HINTS) or _guess_code(row)
        name = _pick(row, NAME_KEYS, NAME_HINTS)
        short = _pick(row, SHORT_KEYS, SHORT_HINTS)
        if not code or not (name or short):
            continue
        companies.append(
            TwCompany(
                code=code,
                name=name or short,
                short_name=short or name,
                english_name=_pick(row, ENGLISH_KEYS, ENGLISH_HINTS),
                industry=industry_label(_pick(row, INDUSTRY_KEYS, INDUSTRY_HINTS)),
                source=source,
            )
        )
    return companies


class TwCompanyRegistry:
    """三個來源合併後的公司名錄，含本機快取。"""

    def __init__(self, companies: list[TwCompany]):
        self.companies = companies
        self._by_code: dict[str, TwCompany] = {}
        self._by_name: dict[str, TwCompany] = {}
        for company in sorted(companies, key=lambda c: SOURCE_PRIORITY.get(c.source, 9)):
            self._by_code.setdefault(company.code, company)
            for candidate in (company.short_name, company.name, company.english_name):
                key = normalize_name(candidate)
                if key:
                    self._by_name.setdefault(key, company)
                # 「其祥-KY」這種也建立去掉 -KY 的索引
                if candidate and "-KY" in candidate.upper():
                    alt = normalize_name(re.sub(r"-KY", "", candidate, flags=re.IGNORECASE))
                    if alt:
                        self._by_name.setdefault(alt, company)

    def __len__(self) -> int:
        return len(self.companies)

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for company in self.companies:
            result[company.source] = result.get(company.source, 0) + 1
        return result

    def lookup(self, *candidates: str) -> TwCompany | None:
        """依序用多個名稱候選查詢，找到就回傳。"""
        cleaned = [c.strip() for c in candidates if c and c.strip()]
        for candidate in cleaned:
            if CODE_RE.match(candidate) and candidate in self._by_code:
                return self._by_code[candidate]
        for candidate in cleaned:
            hit = self._by_name.get(normalize_name(candidate))
            if hit:
                return hit
        return self._fuzzy(cleaned)

    def _fuzzy(self, candidates: list[str]) -> TwCompany | None:
        """名稱互為子字串時的寬鬆比對；太短的字串不做，避免誤判。"""
        best: TwCompany | None = None
        best_len = 0
        for candidate in candidates:
            key = normalize_name(candidate)
            if len(key) < 2:
                continue
            for name_key, company in self._by_name.items():
                if len(name_key) < 2:
                    continue
                if key == name_key or key in name_key or name_key in key:
                    score = len(name_key)
                    if score > best_len or (
                        score == best_len
                        and best is not None
                        and SOURCE_PRIORITY.get(company.source, 9)
                        < SOURCE_PRIORITY.get(best.source, 9)
                    ):
                        best, best_len = company, score
        return best

    # --- 建立 / 快取 ---

    @classmethod
    def load(cls, config, force_refresh: bool = False) -> "TwCompanyRegistry":
        cache_path = config.registry_cache_path
        if not force_refresh:
            cached = cls._read_cache(cache_path, config.registry_ttl_hours)
            if cached is not None:
                log.info("使用台股名錄快取（%d 家公司）", len(cached))
                return cached

        sources = (
            ("listed", config.twse_listed_url),
            ("otc", config.tpex_otc_url),
            ("public", config.twse_public_url),
        )
        companies: list[TwCompany] = []
        failures: list[str] = []
        for source, url in sources:
            try:
                rows = _fetch_json(url, config.http_timeout)
            except RegistryError as exc:
                log.warning("下載 %s 名錄失敗：%s", source, exc)
                failures.append(f"{source}: {exc}")
                continue
            parsed = parse_rows(rows, source)
            log.info("%s 名錄取得 %d 家公司（%s）", source, len(parsed), url)
            companies.extend(parsed)

        if not companies:
            stale = cls._read_cache(cache_path, ttl_hours=None)
            if stale is not None:
                log.warning("三個名錄來源都失敗，改用過期快取：%s", "；".join(failures))
                return stale
            raise RegistryError("三個台股名錄來源都取不到資料：" + "；".join(failures))

        registry = cls(companies)
        registry._write_cache(cache_path)
        return registry

    @classmethod
    def _read_cache(cls, path: Path, ttl_hours: int | None) -> "TwCompanyRegistry | None":
        if not path.is_file():
            return None
        if ttl_hours is not None and (time.time() - path.stat().st_mtime) > ttl_hours * 3600:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return cls([TwCompany(**item) for item in payload["companies"]])
        except (json.JSONDecodeError, KeyError, TypeError, OSError) as exc:
            log.warning("台股名錄快取讀取失敗，將重新下載：%s", exc)
            return None

    def _write_cache(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": time.time(),
            "companies": [company.__dict__ for company in self.companies],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _fetch_json(url: str, timeout: int) -> list[dict[str, Any]]:
    try:
        resp = requests.get(
            url, timeout=timeout, headers={"User-Agent": "x-stock-tracker/0.1", "Accept": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise RegistryError(str(exc)) from exc
    except ValueError as exc:
        raise RegistryError(f"回應不是合法 JSON：{exc}") from exc

    if isinstance(data, dict):
        for key in ("data", "result", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        raise RegistryError("回應是 dict 但找不到資料陣列")
    if not isinstance(data, list):
        raise RegistryError(f"非預期的回應型別：{type(data).__name__}")
    return data
