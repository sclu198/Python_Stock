"""主控台輸出的編碼保護。

Windows 的終端機在繁體中文環境是 cp950，裝不下訊息裡的表情符號。
直接印在終端機時 Python 會用 UTF-8（PEP 528）沒問題，但只要輸出被導向
檔案或管線（例如排程器的 >> log），編碼就會退回 cp950，遇到表情符號
會直接丟 UnicodeEncodeError 讓整個程式中斷。

所以這裡統一處理：導向檔案時強制 UTF-8，終端機則保留原編碼但把無法
顯示的字元換成替代字，不讓它中斷程式。
"""

from __future__ import annotations

import sys

MIN_PYTHON = (3, 10)


def setup_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass  # 非標準串流（測試、IDE）就維持原狀


def check_python_version() -> str:
    """Python 太舊時回傳說明文字，版本沒問題則回傳空字串。"""
    if sys.version_info >= MIN_PYTHON:
        return ""
    current = ".".join(str(part) for part in sys.version_info[:3])
    return (
        f"這個程式需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 以上，目前是 {current}。\n"
        "  分析用的 anthropic 套件本身就要求 Python 3.10+，舊版裝不起來。\n"
        "  請到 https://www.python.org/downloads/ 安裝 Python 3.11 或更新版本後重跑。"
    )
