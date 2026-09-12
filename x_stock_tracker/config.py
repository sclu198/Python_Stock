"""設定讀取：全部來自環境變數，支援專案根目錄的 .env 檔。"""

from __future__ import annotations

import locale
import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def read_text_tolerant(path: Path) -> str:
    """讀文字檔，UTF-8 讀不動就退回系統編碼。

    Windows 的記事本之類的編輯器可能把 .env 存成 cp950，硬要 UTF-8 會直接
    丟 UnicodeDecodeError，訊息又看不出是編碼問題，所以這裡多留一條退路。
    """
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", locale.getpreferredencoding(False)):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def load_dotenv(path: Path | None = None) -> None:
    """把 .env 的內容讀進 os.environ，已存在的環境變數不覆蓋。"""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in read_text_tolerant(env_path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass
class Config:
    # --- 資料來源 ---
    x_username: str = "qq_timmy"
    x_source: str = "api"  # api | rss
    x_bearer_token: str = ""
    x_rss_url: str = ""
    lookback_hours: int = 24
    max_posts_per_run: int = 25

    # --- 分析 ---
    anthropic_api_key: str = ""
    model: str = "claude-opus-5"
    effort: str = "high"
    enable_web_search: bool = True
    web_search_max_uses: int = 5

    # --- 推播 ---
    notifier: str = "telegram"  # telegram | line | stdout
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    line_channel_access_token: str = ""
    line_to_user_id: str = ""

    # --- 台股名錄 ---
    twse_listed_url: str = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    tpex_otc_url: str = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
    twse_public_url: str = "https://openapi.twse.com.tw/v1/opendata/t187ap03_P"
    registry_ttl_hours: int = 24

    # --- 檔案位置 ---
    data_dir: Path = field(default_factory=lambda: DEFAULT_DATA_DIR)
    http_timeout: int = 30

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def registry_cache_path(self) -> Path:
        return self.data_dir / "tw_company_registry.json"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        data_dir = _env("DATA_DIR")
        return cls(
            x_username=_env("X_USERNAME", "qq_timmy").lstrip("@"),
            x_source=_env("X_SOURCE", "api").lower(),
            x_bearer_token=_env("X_BEARER_TOKEN"),
            x_rss_url=_env("X_RSS_URL"),
            lookback_hours=_env_int("LOOKBACK_HOURS", 24),
            max_posts_per_run=_env_int("MAX_POSTS_PER_RUN", 25),
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            model=_env("ANTHROPIC_MODEL", "claude-opus-5"),
            effort=_env("ANTHROPIC_EFFORT", "high"),
            enable_web_search=_env_bool("ENABLE_WEB_SEARCH", True),
            web_search_max_uses=_env_int("WEB_SEARCH_MAX_USES", 5),
            notifier=_env("NOTIFIER", "telegram").lower(),
            telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            line_channel_access_token=_env("LINE_CHANNEL_ACCESS_TOKEN"),
            line_to_user_id=_env("LINE_TO_USER_ID"),
            registry_ttl_hours=_env_int("REGISTRY_TTL_HOURS", 24),
            data_dir=Path(data_dir) if data_dir else DEFAULT_DATA_DIR,
            http_timeout=_env_int("HTTP_TIMEOUT", 30),
        )

    def validate(self) -> list[str]:
        """回傳缺少的設定項目描述，空 list 代表可以執行。"""
        problems: list[str] = []
        if self.x_source == "api" and not self.x_bearer_token:
            problems.append("X_BEARER_TOKEN 未設定（X_SOURCE=api 需要 X API Bearer Token）")
        if self.x_source == "rss" and not self.x_rss_url:
            problems.append("X_RSS_URL 未設定（X_SOURCE=rss 需要 RSS 來源網址）")
        if self.x_source not in {"api", "rss"}:
            problems.append(f"X_SOURCE 只接受 api 或 rss，目前是 {self.x_source!r}")
        if not self.anthropic_api_key:
            problems.append("ANTHROPIC_API_KEY 未設定")
        if self.notifier == "telegram":
            if not self.telegram_bot_token:
                problems.append("TELEGRAM_BOT_TOKEN 未設定（跟 Telegram 的 @BotFather 申請）")
            if not self.telegram_chat_id:
                problems.append(
                    "TELEGRAM_CHAT_ID 未設定（執行 python scripts/telegram_get_chat_id.py 取得數字 chat id）"
                )
        if self.notifier == "line":
            if not self.line_channel_access_token:
                problems.append("LINE_CHANNEL_ACCESS_TOKEN 未設定")
            if not self.line_to_user_id:
                problems.append("LINE_TO_USER_ID 未設定（需要 U 開頭的 userId，不是 LINE ID）")
        return problems
