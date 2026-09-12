#!/usr/bin/env python3
"""檢查三個台股開放資料 API 的實際欄位，確認名錄解析有對上。

在自己的電腦執行：
    python scripts/verify_open_data.py

會印出每個來源的原始欄位名稱、第一筆資料，以及解析後的結果。
如果某個來源解析出 0 家公司，把印出來的欄位名稱補進
x_stock_tracker/tw_market/registry.py 的 *_KEYS 常數即可。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from x_stock_tracker.config import Config  # noqa: E402
from x_stock_tracker.tw_market.registry import _fetch_json, parse_rows  # noqa: E402

SOURCES = [
    ("listed", "上市（TWSE）", "twse_listed_url"),
    ("otc", "上櫃（TPEx）", "tpex_otc_url"),
    ("public", "公開發行／興櫃（TWSE）", "twse_public_url"),
]


def main() -> int:
    config = Config.from_env()
    exit_code = 0

    for source, label, attr in SOURCES:
        url = getattr(config, attr)
        print(f"\n{'=' * 70}\n{label}\n{url}\n{'=' * 70}")
        try:
            rows = _fetch_json(url, config.http_timeout)
        except Exception as exc:  # noqa: BLE001 - 診斷腳本，任何錯誤都要看得到
            print(f"❌ 下載失敗：{exc}")
            exit_code = 1
            continue

        print(f"筆數：{len(rows)}")
        if rows:
            print("欄位名稱：")
            for key in rows[0]:
                print(f"  - {key!r}")
            print("\n第一筆資料：")
            print(json.dumps(rows[0], ensure_ascii=False, indent=2)[:1500])

        parsed = parse_rows(rows, source)
        print(f"\n解析結果：{len(parsed)} 家公司")
        if not parsed:
            print("⚠️ 解析不到任何公司，請把上面的欄位名稱補進 registry.py 的 *_KEYS")
            exit_code = 1
        for company in parsed[:3]:
            print(
                f"  {company.code} {company.short_name} / {company.name} "
                f"/ 產業={company.industry} / 英文={company.english_name}"
            )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
