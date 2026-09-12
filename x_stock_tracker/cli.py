"""每日追蹤流程的進入點。

用法：
    python -m x_stock_tracker              # 正式執行，分析後推到 Telegram
    python -m x_stock_tracker --dry-run    # 只印在終端機，不推播也不更新狀態
    python -m x_stock_tracker --check      # 檢查設定與各項連線
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from .config import Config
from .console import check_python_version, setup_console
from .notify import NotifyError, TelegramNotifier, build_notifier
from .report import build_empty_message, build_messages
from .sources import SourceError, build_source
from .state import StateStore
from .tw_market import RegistryError, TwCompanyRegistry

log = logging.getLogger("x_stock_tracker")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x_stock_tracker", description="追蹤 X 帳號貼文，整理成投資摘要推播到 Telegram"
    )
    parser.add_argument("--dry-run", action="store_true", help="只印出結果，不推播、不更新狀態")
    parser.add_argument("--since-id", default="", help="只抓這個貼文 ID 之後的貼文")
    parser.add_argument("--limit", type=int, default=0, help="最多處理幾則貼文")
    parser.add_argument("--refresh-registry", action="store_true", help="強制重新下載台股名錄")
    parser.add_argument("--notify-empty", action="store_true", help="沒有新貼文時也推播一則通知")
    parser.add_argument("--check", action="store_true", help="檢查設定與連線後結束")
    parser.add_argument("-v", "--verbose", action="store_true", help="輸出除錯訊息")
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_console()
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    version_problem = check_python_version()
    if version_problem:
        log.error("%s", version_problem)
        return 2

    config = Config.from_env()
    if args.dry_run and config.notifier != "stdout":
        config.notifier = "stdout"

    if args.check:
        return run_check(config)

    problems = config.validate()
    if problems:
        for problem in problems:
            log.error("設定不完整：%s", problem)
        log.error("請參考 .env.example 與 docs/SETUP.md 補齊設定")
        return 2

    state = StateStore(config.state_path)

    try:
        posts = build_source(config, state).fetch(since_id=args.since_id or state.last_post_id)
    except SourceError as exc:
        log.error("抓取貼文失敗：%s", exc)
        return 1

    posts = [p for p in posts if not state.is_seen(p.id)]
    if args.limit:
        posts = posts[-args.limit :]
    elif len(posts) > config.max_posts_per_run:
        posts = posts[-config.max_posts_per_run :]

    now = datetime.now().astimezone()
    notifier = build_notifier(config)

    if not posts:
        log.info("沒有新貼文")
        if args.notify_empty:
            notifier.send([build_empty_message(config.x_username, now)])
        if not args.dry_run:
            state.set_last_run(now.isoformat())
            state.save()
        return 0

    log.info("準備分析 %d 則新貼文", len(posts))

    try:
        registry = TwCompanyRegistry.load(config, force_refresh=args.refresh_registry)
        log.info("台股名錄：%s", registry.counts())
    except RegistryError as exc:
        log.warning("台股名錄無法使用，股票代號將只依模型判斷：%s", exc)
        registry = None

    try:
        from .analysis import PostAnalyzer
    except ImportError as exc:
        log.error("載入分析模組失敗（anthropic 套件沒裝好？）：%s", exc)
        log.error("請在專案目錄執行：pip install -r requirements.txt")
        return 2

    analyses = PostAnalyzer(config, registry).analyze_all(posts)
    messages = build_messages(
        analyses, config.x_username, now, max_chars=notifier.max_message_chars
    )

    try:
        notifier.send(messages)
    except NotifyError as exc:
        log.error("推播失敗：%s", exc)
        return 1

    if not args.dry_run:
        state.mark_seen([p.id for p in posts])
        state.set_last_run(now.isoformat())
        state.save()
        log.info("狀態已更新：%s", config.state_path)

    failed = [a for a in analyses if a.error]
    if failed:
        log.warning("%d 則貼文分析失敗，已在訊息中標註", len(failed))
    return 0


def run_check(config: Config) -> int:
    """逐項檢查設定與連線。

    設定沒填齊也照樣執行：這支指令就是設定過程中用來看「還差什麼」的，
    缺什麼就標示並略過該項，不會整個拒絕執行。
    """
    problems = config.validate()
    ok = not problems
    for problem in problems:
        log.warning("⚠️ 尚未完成：%s", problem)

    try:
        registry = TwCompanyRegistry.load(config, force_refresh=True)
        counts = registry.counts()
        labels = {"listed": "上市", "otc": "上櫃", "public": "公開發行／興櫃"}
        missing = [labels[key] for key in labels if not counts.get(key)]
        if missing:
            log.warning(
                "⚠️ 台股名錄缺少：%s —— 這類公司會被誤判為「未上市」，請稍後重跑 --check",
                "、".join(missing),
            )
            ok = False
        log.info(
            "%s 台股名錄：%s，共 %d 家",
            "⚠️" if missing else "✅",
            {labels[k]: v for k, v in counts.items()},
            len(registry),
        )
        for probe in ("台積電", "聯發科", "2330"):
            hit = registry.lookup(probe)
            log.info("   查詢 %s -> %s", probe, f"{hit.code} {hit.name}" if hit else "查無")
    except RegistryError as exc:
        log.error("❌ 台股名錄：%s", exc)
        ok = False

    if (config.x_source == "api" and config.x_bearer_token) or (
        config.x_source == "rss" and config.x_rss_url
    ):
        try:
            posts = build_source(config, StateStore(config.state_path)).fetch()
            log.info("✅ 貼文來源（%s）：取得 %d 則", config.x_source, len(posts))
        except SourceError as exc:
            log.error("❌ 貼文來源：%s", exc)
            ok = False
    else:
        log.warning("⏭ 貼文來源：尚未設定，略過")

    if config.notifier == "telegram":
        if config.telegram_bot_token:
            try:
                bot_name = TelegramNotifier(config).verify()
                log.info("✅ Telegram：token 有效，bot 是 @%s", bot_name)
            except NotifyError as exc:
                log.error("❌ Telegram：%s", exc)
                ok = False
        else:
            log.warning("⏭ Telegram：尚未設定 token，略過")
    elif config.notifier == "line":
        if config.line_to_user_id.startswith("U"):
            log.info("✅ LINE 設定：userId 格式正確")
        else:
            log.error("❌ LINE 設定：LINE_TO_USER_ID 必須是 U 開頭的 userId，不是 LINE ID")
            ok = False

    if config.anthropic_api_key:
        log.info(
            "✅ Anthropic：金鑰已設定，模型 %s（effort=%s，web search=%s）",
            config.model, config.effort, config.enable_web_search,
        )
    else:
        log.warning("⏭ Anthropic：尚未設定 ANTHROPIC_API_KEY，略過")

    log.info("檢查結果：%s", "全部就緒，可以執行 --dry-run" if ok else "還有項目未完成，見上面的 ⚠️ 與 ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
