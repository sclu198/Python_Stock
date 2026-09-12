#!/usr/bin/env python3
"""取得自己的 Telegram chat id。

Telegram 的 bot 沒辦法用 @使用者名稱 主動私訊你，一定要用數字 chat id。
取得方式：

 1. 在 Telegram 裡找 @BotFather，送 /newbot 建立一個 bot，把它給的 token
    填進 .env 的 TELEGRAM_BOT_TOKEN
 2. 在 Telegram 搜尋你剛建立的 bot，按下 Start（或隨便傳一句話給它）
 3. 執行：python scripts/telegram_get_chat_id.py
 4. 把印出來的 chat id 填進 .env 的 TELEGRAM_CHAT_ID

如果印出「目前沒有任何訊息」，代表第 2 步還沒做，或訊息已經被先前的
getUpdates 取走——再傳一則新訊息給 bot 就好。
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from x_stock_tracker.config import Config  # noqa: E402


def main() -> int:
    config = Config.from_env()
    if not config.telegram_bot_token:
        print("❌ 請先在 .env 設定 TELEGRAM_BOT_TOKEN（跟 @BotFather 申請）")
        return 2

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/getUpdates"
    try:
        resp = requests.get(url, timeout=config.http_timeout)
    except requests.RequestException as exc:
        print(f"❌ 連線 Telegram 失敗：{exc}")
        return 1

    body = resp.json() if resp.content else {}
    if not body.get("ok"):
        print(f"❌ Telegram 回應失敗（{resp.status_code}）：{body.get('description', resp.text[:200])}")
        return 1

    seen: dict[str, str] = {}
    for update in body.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        who = chat.get("username") or chat.get("title") or chat.get("first_name", "")
        seen[str(chat_id)] = f"{chat.get('type', '')} {('@' + who) if who else ''}".strip()

    if not seen:
        print("⚠️ 目前沒有任何訊息。請先在 Telegram 對你的 bot 按 Start 或傳一則訊息，再跑一次。")
        return 1

    print("✅ 找到以下對話：\n")
    for chat_id, description in seen.items():
        print(f"  chat id = {chat_id}   （{description}）")
    print("\n把要收通知的那一個填進 .env：")
    print(f"TELEGRAM_CHAT_ID={next(iter(seen))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
