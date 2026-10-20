import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from winsmith.unattend import (custom_error, custom_files, custom_name, drivers_error, make_patch_script,
                               make_unattend, remap_reg)

NS = {"u": "urn:schemas-microsoft-com:unattend"}


class ArchTests(unittest.TestCase):
    def test_every_component_names_the_arch(self):
        for arch in ("amd64", "arm64"):
            root = ET.fromstring(make_unattend({"unattended": True, "user": "U"}, ["hwchecks", "tracking"], arch))
            comps = root.findall(".//u:component", NS)
            self.assertTrue(comps)
            self.assertEqual({c.get("processorArchitecture") for c in comps}, {arch})

    def test_default_is_amd64(self):
        self.assertIn('processorArchitecture="amd64"', make_unattend({}, ["hwchecks"]))


class CustomScriptTests(unittest.TestCase):
    def files(self, d):
        a, b, c = Path(d) / "a.reg", Path(d) / "b.ps1", Path(d) / "c.txt"
        for f in (a, b, c):
            f.write_text("x")
        return str(a), str(b), str(c)

    def test_custom_files_keeps_existing_allowed_unique(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, c = self.files(d)
            got = custom_files({"custom": [a, b, a, c, str(Path(d) / "gone.ps1"), 5]})
        self.assertEqual(got, [a, b])

    def test_custom_error(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, c = self.files(d)
            self.assertIsNone(custom_error({"custom": [a, b]}))
            self.assertIn("Only .ps1 and .reg", custom_error({"custom": [c]}))
            self.assertIn("not found", custom_error({"custom": [str(Path(d) / "gone.ps1")]}))

    def test_drivers_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(drivers_error({}))
            self.assertIn("not found", drivers_error({"drivers": str(Path(d) / "nope")}))
            self.assertIn("No .inf", drivers_error({"drivers": d}))
            (Path(d) / "sub").mkdir()
            (Path(d) / "sub" / "x.inf").write_text("")
            self.assertIsNone(drivers_error({"drivers": d}))

    def test_remap_reg_utf16_and_utf8(self):
        text = "Windows Registry Editor Version 5.00\r\n\r\n[HKEY_CURRENT_USER\\Software\\X]\r\n[-hkcu\\Y]\r\n[HKEY_LOCAL_MACHINE\\Z]\r\n"
        for raw in (text.encode("utf-16"), text.encode("utf-8"), b"\xef\xbb\xbf" + text.encode("utf-8")):
            out = remap_reg(raw)
            self.assertTrue(out.startswith(b"\xff\xfe"))
            got = out.decode("utf-16")
            self.assertIn("[HKEY_USERS\\WS_DEFAULT\\Software\\X]", got)
            self.assertIn("[-HKEY_USERS\\WS_DEFAULT\\Y]", got)
            self.assertIn("[HKEY_LOCAL_MACHINE\\Z]", got)

    def test_custom_name_is_ascii_and_numbered(self):
        self.assertEqual(custom_name(2, "C:/x/My Tweaks é.PS1"), "custom-2-My_Tweaks__.ps1")

    def test_patch_script_runs_custom_files_with_no_patches(self):
        script = make_patch_script([], ["custom-1-a.reg", "custom-2-b.ps1"])
        self.assertIn("Reg import 'C:\\Windows\\Setup\\Scripts\\custom-1-a.reg'", script)
        self.assertIn("-File', 'C:\\Windows\\Setup\\Scripts\\custom-2-b.ps1'", script)
        self.assertIn("WaitForExit(600000)", script)
        self.assertLess(script.index("reg.exe load"), script.index("custom-1-a.reg"))
        self.assertLess(script.index("custom-2-b.ps1"), script.index("reg.exe unload"))

    def test_unattend_runs_the_script_for_custom_files_only(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "b.ps1"
            f.write_text("x")
            self.assertIn("winsmith.ps1", make_unattend({"custom": [str(f)]}, []))
        self.assertNotIn("winsmith.ps1", make_unattend({}, []))


if __name__ == "__main__":
    unittest.main()
