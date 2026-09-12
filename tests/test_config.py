"""設定讀取與環境檢查的測試。"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from x_stock_tracker import console
from x_stock_tracker.config import Config, load_dotenv, read_text_tolerant


class TestReadTextTolerant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "f.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_utf8(self):
        self.path.write_bytes("中文 TOKEN=abc".encode("utf-8"))
        self.assertEqual(read_text_tolerant(self.path), "中文 TOKEN=abc")

    def test_strips_utf8_bom(self):
        self.path.write_bytes("﻿TOKEN=abc".encode("utf-8"))
        self.assertEqual(read_text_tolerant(self.path), "TOKEN=abc")

    def test_falls_back_to_legacy_windows_encoding(self):
        # 記事本存成 cp950 的情況，不該丟 UnicodeDecodeError
        self.path.write_bytes("# 中文註解\nTOKEN=abc".encode("cp950"))
        text = read_text_tolerant(self.path)
        self.assertIn("TOKEN=abc", text)


class TestLoadDotenv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / ".env"
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)
        self.tmp.cleanup()

    def test_loads_values_and_skips_comments(self):
        self.path.write_text("# 註解\n\nTELEGRAM_CHAT_ID=123\nQUOTED=\"abc\"\n", encoding="utf-8")
        os.environ.pop("TELEGRAM_CHAT_ID", None)
        os.environ.pop("QUOTED", None)
        load_dotenv(self.path)
        self.assertEqual(os.environ["TELEGRAM_CHAT_ID"], "123")
        self.assertEqual(os.environ["QUOTED"], "abc")

    def test_does_not_override_existing_env(self):
        self.path.write_text("TELEGRAM_CHAT_ID=fromfile\n", encoding="utf-8")
        os.environ["TELEGRAM_CHAT_ID"] = "fromenv"
        load_dotenv(self.path)
        self.assertEqual(os.environ["TELEGRAM_CHAT_ID"], "fromenv")

    def test_cp950_env_file_does_not_crash(self):
        self.path.write_bytes("# 中文註解\nTELEGRAM_CHAT_ID=987\n".encode("cp950"))
        os.environ.pop("TELEGRAM_CHAT_ID", None)
        load_dotenv(self.path)
        self.assertEqual(os.environ["TELEGRAM_CHAT_ID"], "987")


class TestPythonVersionCheck(unittest.TestCase):
    def test_passes_on_supported_version(self):
        self.assertEqual(console.check_python_version(), "")

    def test_explains_when_too_old(self):
        with mock.patch.object(console, "MIN_PYTHON", (99, 0)):
            message = console.check_python_version()
        self.assertIn("99.0", message)
        self.assertIn("anthropic", message)


class TestSetupConsole(unittest.TestCase):
    def test_forces_utf8_when_output_is_redirected(self):
        stream = mock.Mock()
        stream.isatty.return_value = False
        with mock.patch.object(console.sys, "stdout", stream), \
             mock.patch.object(console.sys, "stderr", stream):
            console.setup_console()
        stream.reconfigure.assert_called_with(encoding="utf-8", errors="replace")

    def test_survives_streams_without_reconfigure(self):
        stream = mock.Mock(spec=[])  # 沒有 isatty / reconfigure
        with mock.patch.object(console.sys, "stdout", stream), \
             mock.patch.object(console.sys, "stderr", stream):
            console.setup_console()  # 不該拋錯


if __name__ == "__main__":
    unittest.main()
