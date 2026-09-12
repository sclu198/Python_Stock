"""模組進入點。

環境檢查必須在載入 cli 之前做完：cli 會連帶載入需要 anthropic 的分析模組，
Python 版本不合或套件沒裝時會先炸在 import，使用者就看不到我們寫的說明。
"""

import sys

from .console import check_python_version, setup_console

setup_console()

_problem = check_python_version()
if _problem:
    print(f"環境不符：{_problem}", file=sys.stderr)
    sys.exit(2)

try:
    from .cli import main
except ImportError as exc:
    print(
        f"缺少相依套件：{exc}\n"
        "  請在專案目錄執行：pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(main())
