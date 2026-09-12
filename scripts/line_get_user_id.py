#!/usr/bin/env python3
"""臨時 webhook server，用來取得自己的 LINE userId。

LINE 的推播 API 不能用 LINE ID（brucelu215 這種），只認 U 開頭的 userId。
最快的方法是 LINE Developers Console → Messaging API 分頁 → Your user ID；
如果那裡看不到，就用這支腳本：

 1. python scripts/line_get_user_id.py           # 預設監聽 0.0.0.0:8000
 2. 另開終端機：ngrok http 8000
 3. 把 ngrok 的 https 網址 + /webhook 填進 LINE Developers Console 的 Webhook URL
 4. 用手機對這個 bot 傳一則訊息，userId 就會印在終端機上

設了 LINE_CHANNEL_SECRET 就會順便驗證 X-Line-Signature。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from x_stock_tracker.config import load_dotenv  # noqa: E402

load_dotenv()
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 規定的名稱
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        if CHANNEL_SECRET and not _valid_signature(body, self.headers.get("X-Line-Signature", "")):
            print("⚠️ 簽章驗證失敗，忽略這個請求")
            self.send_response(400)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return

        for event in payload.get("events", []):
            source = event.get("source", {})
            user_id = source.get("userId", "")
            if user_id:
                print(f"\n✅ 找到 userId：{user_id}")
                print("把它填進 .env：")
                print(f"LINE_TO_USER_ID={user_id}\n")

    def log_message(self, fmt: str, *args) -> None:
        return  # 關掉預設的存取紀錄，畫面才乾淨


def _valid_signature(body: bytes, signature: str) -> bool:
    digest = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode("utf-8"), signature)


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    print(f"監聽 http://0.0.0.0:{port}/webhook（Ctrl+C 結束）")
    if not CHANNEL_SECRET:
        print("（未設定 LINE_CHANNEL_SECRET，略過簽章驗證）")
    server = HTTPServer(("0.0.0.0", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n結束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
