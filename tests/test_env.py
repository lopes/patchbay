import os
import tempfile
import unittest
from pathlib import Path

from patchbay.config import _load_env_file


class LoadEnvFileTest(unittest.TestCase):
    def setUp(self):
        self._prev_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._prev_env)

    def _write(self, contents: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False)
        tmp.write(contents)
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return Path(tmp.name)

    def test_basic_key_value(self):
        os.environ.pop("PATCHBAY_TEST_KEY", None)
        _load_env_file(self._write("PATCHBAY_TEST_KEY=hello\n"))
        self.assertEqual(os.environ["PATCHBAY_TEST_KEY"], "hello")

    def test_comment_ignored(self):
        os.environ.pop("PATCHBAY_COMMENTED", None)
        _load_env_file(self._write("# PATCHBAY_COMMENTED=nope\n"))
        self.assertNotIn("PATCHBAY_COMMENTED", os.environ)

    def test_blank_lines_ignored(self):
        os.environ.pop("PATCHBAY_BLANK", None)
        _load_env_file(self._write("\n\n\nPATCHBAY_BLANK=ok\n\n"))
        self.assertEqual(os.environ["PATCHBAY_BLANK"], "ok")

    def test_export_prefix_stripped(self):
        os.environ.pop("PATCHBAY_EXP", None)
        _load_env_file(self._write("export PATCHBAY_EXP=yep\n"))
        self.assertEqual(os.environ["PATCHBAY_EXP"], "yep")

    def test_quoted_value_stripped(self):
        os.environ.pop("PATCHBAY_Q", None)
        _load_env_file(self._write('PATCHBAY_Q="quoted"\n'))
        self.assertEqual(os.environ["PATCHBAY_Q"], "quoted")

    def test_single_quotes_stripped(self):
        os.environ.pop("PATCHBAY_SQ", None)
        _load_env_file(self._write("PATCHBAY_SQ='single'\n"))
        self.assertEqual(os.environ["PATCHBAY_SQ"], "single")

    def test_real_env_wins(self):
        os.environ["PATCHBAY_WIN"] = "real"
        _load_env_file(self._write("PATCHBAY_WIN=from_file\n"))
        self.assertEqual(os.environ["PATCHBAY_WIN"], "real")

    def test_line_without_equals_ignored(self):
        os.environ.pop("PATCHBAY_NOEQ", None)
        _load_env_file(self._write("this is not a kv pair\nPATCHBAY_NOEQ=ok\n"))
        self.assertEqual(os.environ["PATCHBAY_NOEQ"], "ok")

    def test_missing_file_is_silent(self):
        _load_env_file(Path("/tmp/definitely-does-not-exist-patchbay-xxx"))  # no raise


if __name__ == "__main__":
    unittest.main()
