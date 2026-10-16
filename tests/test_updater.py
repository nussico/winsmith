import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from winsmith import updater

RELEASE = {
    "tag_name": "v0.3.0",
    "html_url": "https://github.com/nussico/winsmith/releases/tag/v0.3.0",
    "assets": [
        {"name": "notes.txt", "browser_download_url": "https://github.com/nussico/winsmith/releases/download/v0.3.0/notes.txt", "size": 5},
        {"name": "Winsmith.exe", "size": 11,
         "browser_download_url": "https://github.com/nussico/winsmith/releases/download/v0.3.0/Winsmith.exe"},
    ],
}


class VersionTests(unittest.TestCase):
    def test_is_newer(self):
        self.assertTrue(updater.is_newer("0.2.10", "0.2.9"))
        self.assertTrue(updater.is_newer("v0.3.0", "0.2.2"))
        self.assertFalse(updater.is_newer("0.2.2", "0.2.2"))
        self.assertFalse(updater.is_newer("0.2.1", "0.2.2"))

    def test_garbage_is_never_newer(self):
        self.assertFalse(updater.is_newer("nightly", "0.2.2"))
        self.assertFalse(updater.is_newer("", "0.2.2"))


class ReleaseTests(unittest.TestCase):
    def test_parse_release(self):
        rel = updater.parse_release(RELEASE)
        self.assertEqual(rel["version"], "0.3.0")
        self.assertEqual(rel["page"], RELEASE["html_url"])
        self.assertTrue(rel["asset_url"].endswith("/Winsmith.exe"))
        self.assertEqual(rel["size"], 11)

    def test_parse_release_without_exe_has_no_asset(self):
        data = {**RELEASE, "assets": []}
        self.assertIsNone(updater.parse_release(data)["asset_url"])

    def test_parse_release_rejects_foreign_asset_host(self):
        data = {**RELEASE, "assets": [{"name": "Winsmith.exe", "size": 11,
                                       "browser_download_url": "https://evil.example/Winsmith.exe"}]}
        self.assertIsNone(updater.parse_release(data)["asset_url"])

    def test_parse_release_bad_data(self):
        self.assertIsNone(updater.parse_release({}))
        self.assertIsNone(updater.parse_release(None))

    def test_latest_release_returns_none_on_error(self):
        with mock.patch.object(updater, "_get_json", side_effect=OSError("offline")):
            self.assertIsNone(updater.latest_release())

    def test_check_only_reports_newer(self):
        with mock.patch.object(updater, "_get_json", return_value=RELEASE):
            self.assertEqual(updater.check("0.2.2")["version"], "0.3.0")
            self.assertIsNone(updater.check("0.3.0"))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_download_ok_reports_progress(self):
        seen = []
        with mock.patch.object(updater, "_open", return_value=io.BytesIO(b"hello world")):
            dest = updater.download(RELEASE["assets"][1]["browser_download_url"], self.dir / "new.exe", 11,
                                    seen.append)
        self.assertEqual(dest.read_bytes(), b"hello world")
        self.assertEqual(seen[-1], 1.0)

    def test_download_wrong_size_is_deleted(self):
        with mock.patch.object(updater, "_open", return_value=io.BytesIO(b"short")):
            with self.assertRaisesRegex(RuntimeError, "size"):
                updater.download(RELEASE["assets"][1]["browser_download_url"], self.dir / "new.exe", 11)
        self.assertFalse((self.dir / "new.exe").exists())

    def test_download_refuses_foreign_url(self):
        with self.assertRaises(RuntimeError):
            updater.download("https://evil.example/Winsmith.exe", self.dir / "new.exe", 11)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cur = self.dir / "Winsmith.exe"
        self.new = self.dir / "Winsmith.new.exe"
        self.cur.write_bytes(b"old")
        self.new.write_bytes(b"new")

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_swaps_and_keeps_old(self):
        updater.apply(self.new, self.cur)
        self.assertEqual(self.cur.read_bytes(), b"new")
        self.assertEqual((self.dir / "Winsmith.old.exe").read_bytes(), b"old")
        self.assertFalse(self.new.exists())

    def test_apply_rolls_back_when_move_fails(self):
        real = Path.replace

        def flaky(p, target):
            if p == self.new:
                raise OSError("locked")
            return real(p, target)

        with mock.patch.object(Path, "replace", flaky):
            with self.assertRaises(OSError):
                updater.apply(self.new, self.cur)
        self.assertEqual(self.cur.read_bytes(), b"old")
        self.assertFalse((self.dir / "Winsmith.old.exe").exists())

    def test_apply_replaces_stale_old_file(self):
        (self.dir / "Winsmith.old.exe").write_bytes(b"stale")
        updater.apply(self.new, self.cur)
        self.assertEqual((self.dir / "Winsmith.old.exe").read_bytes(), b"old")

    def test_cleanup_old(self):
        (self.dir / "Winsmith.old.exe").write_bytes(b"x")
        updater.cleanup_old(self.cur)
        self.assertFalse((self.dir / "Winsmith.old.exe").exists())
        updater.cleanup_old(self.cur)  # nothing left: no error


class DueTests(unittest.TestCase):
    def test_due_once_a_day(self):
        self.assertTrue(updater.due(0, now=100000))
        self.assertFalse(updater.due(100000 - 3600, now=100000))
        self.assertTrue(updater.due(100000 - 90000, now=100000))


if __name__ == "__main__":
    unittest.main()
