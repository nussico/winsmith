import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from winsmith.patches import PATCHES
from winsmith.verify import make_verify_script


class VerifyTests(unittest.TestCase):
    def test_one_check_per_entry(self):
        s = make_verify_script(list(PATCHES))
        regs = sum(len(p["reg"]) for p in PATCHES.values())
        apps = sum(len(p["apps"]) for p in PATCHES.values())
        self.assertEqual(s.count("\nCheck "), regs + apps)
        self.assertTrue(s.isascii())
        self.assertEqual(s.count("{"), s.count("}"))

    def test_check_kinds(self):
        s = make_verify_script(["tracking", "onedrive", "classicmenu", "stickykeys", "bloatapps"])
        self.assertIn(r"'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\DataCollection'", s)
        self.assertIn("'AllowTelemetry') -eq 0", s)
        self.assertIn(r"Registry::HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run", s)  # DEFAULT
        self.assertIn("Absent ", s)  # '-' deletes the value
        self.assertIn("Test-Path -LiteralPath", s)  # '@' default value
        self.assertIn("-eq '506'", s)
        self.assertIn("Get-AppxPackage -Name 'Clipchamp.Clipchamp'", s)
        self.assertNotIn("WindowsStore", s)

    @unittest.skipUnless(sys.platform == "win32", "needs PowerShell")
    def test_script_parses(self):
        fd, f = tempfile.mkstemp(suffix=".ps1")
        try:
            with open(fd, "w", encoding="ascii", newline="") as fh:
                fh.write(make_verify_script(list(PATCHES)))
            cmd = (f"$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile('{f}', [ref]$null, [ref]$e);"
                   " $e | ForEach-Object { $_.Message }")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                                 timeout=60).stdout.strip()
        finally:
            Path(f).unlink(missing_ok=True)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
