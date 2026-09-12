"""環境不完整時的行為：沒裝 anthropic、Python 版本太舊。"""

import subprocess
import sys
import unittest
from unittest import mock


def _reload_package():
    for name in [n for n in sys.modules if n.startswith("x_stock_tracker")]:
        del sys.modules[name]


class TestWithoutAnthropic(unittest.TestCase):
    """anthropic 只有分析階段才需要，不該擋住設定檢查與推播測試。"""

    def setUp(self):
        _reload_package()
        self.addCleanup(_reload_package)

    def test_cli_imports_without_anthropic(self):
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            from x_stock_tracker import cli

            self.assertTrue(callable(cli.main))

    def test_check_runs_without_anthropic(self):
        # 重點是沒有因為 import anthropic 就崩潰；名錄下載要 mock 掉不連外網
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            from x_stock_tracker import cli
            from x_stock_tracker.tw_market import RegistryError

            with mock.patch.dict("os.environ", {"NOTIFIER": "stdout", "X_SOURCE": "rss"}, clear=False), \
                 mock.patch.object(
                     cli.TwCompanyRegistry, "load", side_effect=RegistryError("測試不連網")
                 ):
                code = cli.main(["--check"])
        self.assertIn(code, (0, 1, 2))


class TestEntryPointGuards(unittest.TestCase):
    def test_module_entry_point_reports_missing_dependency(self):
        script = (
            "import sys, runpy;"
            "sys.modules['anthropic'] = None;"
            "sys.modules['requests'] = None;"
            "runpy.run_module('x_stock_tracker', run_name='__main__')"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("pip install -r requirements.txt", result.stderr)


if __name__ == "__main__":
    unittest.main()
