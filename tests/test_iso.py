import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from winsmith import iso
from winsmith.iso import make_writable


class IsoTests(unittest.TestCase):
    def test_copied_cd_tree_can_be_deleted(self):
        # A mounted ISO is read-only, root included; copytree copies that onto the work folder itself.
        tmp = Path(tempfile.mkdtemp())
        src, dest = tmp / "cd", tmp / "work"
        (src / "sources").mkdir(parents=True)
        (src / "sources" / "a.txt").write_text("x")
        for p in (src / "sources" / "a.txt", src / "sources", src):
            os.chmod(p, stat.S_IREAD)
        try:
            dest.mkdir()
            shutil.copytree(src, dest, dirs_exist_ok=True)
            make_writable(dest)
            shutil.rmtree(dest)
            self.assertFalse(dest.exists())
        finally:
            for root, dirs, files in os.walk(tmp):
                for n in dirs + files:
                    os.chmod(os.path.join(root, n), stat.S_IWRITE | stat.S_IREAD)
            shutil.rmtree(tmp, ignore_errors=True)


    def test_install_oscdimg_only_deployment_tools(self):
        with mock.patch.object(iso, "_run") as run, mock.patch.object(iso, "_find_oscdimg", return_value="x"):
            iso.install_oscdimg(lambda m: None)
        cmd = run.call_args[0][0]
        self.assertIn("Microsoft.WindowsADK", cmd)
        self.assertEqual(cmd[cmd.index("--override") + 1], "/quiet /norestart /features OptionId.DeploymentTools")

    def test_install_oscdimg_reports_when_still_missing(self):
        # e.g. the ADK is installed without Deployment Tools: winget fails with "already installed".
        with mock.patch.object(iso, "_run", side_effect=RuntimeError("winget failed")), \
                mock.patch.object(iso, "_find_oscdimg", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Deployment Tools"):
                iso.install_oscdimg(lambda m: None)

    def test_install_oscdimg_includes_winget_error(self):
        with mock.patch.object(iso, "_run", side_effect=RuntimeError("user declined UAC")), \
                mock.patch.object(iso, "_find_oscdimg", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "user declined UAC"):
                iso.install_oscdimg(lambda m: None)

    def test_run_times_out(self):
        import subprocess
        import sys
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            with mock.patch.object(iso.time, "monotonic", side_effect=[0, 1000]):
                iso._run([sys.executable, "-c", "import time; time.sleep(30)"], lambda m: None, timeout=60)

    def test_find_oscdimg_checks_arm64_and_program_files(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / r"Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\arm64\Oscdimg\oscdimg.exe"
            exe.parent.mkdir(parents=True)
            exe.write_text("")
            env = {"ProgramFiles(x86)": str(Path(d) / "none"), "ProgramFiles": d, "PROCESSOR_ARCHITECTURE": "ARM64"}
            with mock.patch.object(iso.shutil, "which", return_value=None), mock.patch.dict(os.environ, env):
                self.assertEqual(iso._find_oscdimg(), str(exe))

    def _tree(self, root, *files):
        for f in files:
            p = Path(root) / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")

    def test_detect_arch(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(iso.detect_arch(d), "amd64")
            self._tree(d, "EFI/Boot/bootaa64.efi")
            self.assertEqual(iso.detect_arch(d), "arm64")

    def test_pack_without_bios_boot_is_uefi_only(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(iso, "_run") as run,                 mock.patch.object(iso, "_find_oscdimg", return_value="oscdimg"):
            self._tree(d, "efi/microsoft/boot/efisys.bin")
            iso.pack(Path(d), Path(d) / "out.iso", lambda m: None)
            cmd = " ".join(map(str, run.call_args[0][0]))
        self.assertNotIn("etfsboot", cmd)
        if iso.IS_WINDOWS:
            self.assertIn("-bootdata:1#pEF", cmd)
        else:
            self.assertNotIn("-b ", cmd)

    def test_pack_with_bios_boot_keeps_both(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(iso, "_run") as run,                 mock.patch.object(iso, "_find_oscdimg", return_value="oscdimg"):
            self._tree(d, "efi/microsoft/boot/efisys.bin", "boot/etfsboot.com")
            iso.pack(Path(d), Path(d) / "out.iso", lambda m: None)
            cmd = " ".join(map(str, run.call_args[0][0]))
        self.assertIn("etfsboot", cmd)

    def test_space_error(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.iso"
            src.write_bytes(b"x" * 10)
            self.assertIsNone(iso.space_error(src, Path(d) / "b.iso"))
            full = mock.Mock(free=2**30)
            with mock.patch.object(iso.shutil, "disk_usage", return_value=full):
                self.assertRegex(iso.space_error(src, Path(d) / "new" / "b.iso"), "Not enough free space")

    def test_edition_error(self):
        names = ["Windows 11 Home", "Windows 11 Pro"]
        self.assertIsNone(iso.edition_error("Pro", names))
        self.assertIsNone(iso.edition_error("", names))
        self.assertIsNone(iso.edition_error("Pro", None))  # unreadable image: let Setup decide
        self.assertEqual(iso.edition_error("Education", names),
                         "This ISO has no Windows 11 Education. It has: Home, Pro.")
        self.assertEqual(iso.editions_in(names), ["Home", "Pro"])

    def test_build_copies_drivers_and_custom_scripts(self):
        from tests.test_wim import make_wim
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "drv").mkdir()
            (d / "drv" / "rst.inf").write_text("x")
            (d / "a.reg").write_text("[HKEY_CURRENT_USER\\Software\\X]\n", encoding="utf-8")
            (d / "b.ps1").write_text("echo hi")
            seen = {}

            def fake_extract(src, dest, log, cancel=None):
                (Path(dest) / "sources").mkdir(parents=True)
                (Path(dest) / "sources" / "install.wim").write_bytes(make_wim(["Windows 11 Pro"]))
                self._tree(dest, "efi/boot/bootaa64.efi")

            def fake_pack(src, out, log, cancel=None):
                seen["inf"] = (Path(src) / "$WinpeDriver$" / "rst.inf").exists()
                seen["xml"] = (Path(src) / "autounattend.xml").read_text(encoding="utf-8")
                scripts = Path(src) / "sources" / "$OEM$" / "$$" / "Setup" / "Scripts"
                seen["files"] = sorted(p.name for p in scripts.iterdir())
                seen["reg"] = (scripts / "custom-1-a.reg").read_bytes()
                Path(out).write_bytes(b"iso")

            (d / "in.iso").write_bytes(b"x")
            settings = {"drivers": str(d / "drv"), "custom": [str(d / "a.reg"), str(d / "b.ps1")], "edition": "Pro"}
            with mock.patch.object(iso, "extract", fake_extract), mock.patch.object(iso, "pack", fake_pack), \
                    mock.patch.object(iso, "missing_tools", return_value=[]):
                iso.build(d / "in.iso", d / "out" / "o.iso", settings, [], lambda m: None)
                with self.assertRaisesRegex(RuntimeError, "no Windows 11 Home"):
                    iso.build(d / "in.iso", d / "out" / "o2.iso", {**settings, "edition": "Home"}, [], lambda m: None)
        self.assertTrue(seen["inf"])
        self.assertIn('processorArchitecture="arm64"', seen["xml"])
        self.assertEqual(seen["files"], ["custom-1-a.reg", "custom-2-b.ps1", "winsmith.ps1"])
        self.assertIn("HKEY_USERS\\WS_DEFAULT\\Software\\X".encode("utf-16-le"), seen["reg"])


if __name__ == "__main__":
    unittest.main()
