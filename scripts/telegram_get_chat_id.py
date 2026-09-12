#!/usr/bin/env python3
"""設定 Telegram 推播：驗證 token、取得 chat id、寫回 .env，並發一則測試訊息。

Telegram 的 bot 沒辦法用 @使用者名稱主動私訊你，一定要用數字 chat id。
完整流程：

 1. 在 Telegram 找 @BotFather 送 /newbot 建立 bot，拿到 token
 2. 在 Telegram 搜尋你的 bot，按下 Start（這步不能跳過）
 3. 執行：

        python scripts/telegram_get_chat_id.py --token 你的token --save

    它會把 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID 寫進 .env，
    並發一則測試訊息到你的 Telegram。

token 已經填進 .env 的話，直接執行 `python scripts/telegram_get_chat_id.py` 就好。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from x_stock_tracker.config import PROJECT_ROOT, Config  # noqa: E402

API_BASE = "https://api.telegram.org"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="取得 Telegram chat id 並完成推播設定")
    parser.add_argument("--token", default="", help="bot token，省略則讀 .env 的 TELEGRAM_BOT_TOKEN")
    parser.add_argument("--save", action="store_true", help="把 token 與 chat id 寫進 .env")
    parser.add_argument("--no-test", action="store_true", help="不要發測試訊息")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config.from_env()
    token = args.token.strip() or config.telegram_bot_token
    if not token:
        print("❌ 沒有 token。請用 --token 指定，或先填進 .env 的 TELEGRAM_BOT_TOKEN")
        return 2

    bot_name = _verify_token(token, config.http_timeout)
    if bot_name is None:
        return 1
    print(f"✅ token 有效，bot 是 @{bot_name}")

    chats = _find_chats(token, config.http_timeout)
    if chats is None:
        return 1
    if not chats:
        print(
            "\n⚠️ 還沒收到任何訊息。\n"
            f"   請在 Telegram 搜尋 @{bot_name}，按下 Start 或隨便傳一句話，再執行一次這個指令。\n"
            "   （如果剛才已經傳過，可能訊息被先前的 getUpdates 取走了，再傳一則新的即可）"
        )
        return 1

    print("\n✅ 找到以下對話：")
    for chat_id, description in chats.items():
        print(f"   chat id = {chat_id}   （{description}）")

    chat_id = next(iter(chats))
    if len(chats) > 1:
        print(f"\n有多個對話，以下使用第一個（{chat_id}）；要用別的就自己填進 .env。")

    if not args.no_test:
        _send_test(token, chat_id, config.http_timeout)

    if args.save:
        _save_env({"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id, "NOTIFIER": "telegram"})
    else:
        print("\n把這些填進 .env（或加上 --save 讓腳本直接寫入）：")
        print(f"NOTIFIER=telegram\nTELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID={chat_id}")

    print("\n下一步：python -m x_stock_tracker --check")
    return 0


def _verify_token(token: str, timeout: int) -> str | None:
    body = _call(f"{API_BASE}/bot{token}/getMe", timeout)
    if body is None:
        return None
    return body.get("result", {}).get("username", "unknown")


def _find_chats(token: str, timeout: int) -> dict[str, str] | None:
    body = _call(f"{API_BASE}/bot{token}/getUpdates", timeout)
    if body is None:
        return None
    chats: dict[str, str] = {}
    for update in body.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        who = chat.get("username") or chat.get("title") or chat.get("first_name", "")
        chats[str(chat_id)] = f"{chat.get('type', '')} {('@' + who) if who else ''}".strip()
    return chats


def _send_test(token: str, chat_id: str, timeout: int) -> None:
    payload = {
        "chat_id": chat_id,
        "text": "✅ 測試訊息：X 貼文投資摘要設定成功，之後每天的摘要會發到這裡。",
        "link_preview_options": {"is_disabled": True},
    }
    try:
        resp = requests.post(f"{API_BASE}/bot{token}/sendMessage", json=payload, timeout=timeout)
    except requests.RequestException as exc:
        print(f"\n⚠️ 測試訊息沒送出去：{exc}")
        return
    if resp.status_code == 200:
        print("\n📨 已發出測試訊息，去 Telegram 看看收到了沒。")
    else:
        description = _description(resp)
        print(f"\n⚠️ 測試訊息失敗（{resp.status_code}）：{description}")


def _save_env(values: dict[str, str], env_path: Path | None = None) -> None:
    """更新 .env 裡的設定；沒有 .env 就從 .env.example 複製一份。"""
    path = env_path or PROJECT_ROOT / ".env"
    if not path.is_file():
        example = PROJECT_ROOT / ".env.example"
        path.write_text(example.read_text(encoding="utf-8") if example.is_file() else "", encoding="utf-8")

    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(values)
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            lines[index] = f"{key}={remaining.pop(key)}"
    lines.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n💾 已寫入 {path}（這個檔案不會被 git 追蹤）")


def _call(url: str, timeout: int) -> dict | None:
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        print(f"❌ 連線 Telegram 失敗：{exc}")
        return None
    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or not body.get("ok"):
        print(f"❌ Telegram 回應失敗（{resp.status_code}）：{_description(resp)}")
        if resp.status_code == 401:
            print("   token 不對，請跟 @BotFather 重新確認，或用 /revoke 產一組新的。")
        return None
    return body


def _description(resp) -> str:
    try:
        return resp.json().get("description", resp.text[:200])
    except ValueError:
        return resp.text[:200]


if __name__ == "__main__":
    sys.exit(main())
