import sys
import unittest
import xml.etree.ElementTree as ET

from winsmith.patches import PATCHES, PRESETS, REMOVE_APPS
from winsmith.unattend import wifi_error, wifi_on, make_wifi_script, app_id_ok, make_apps_script, account_error, auto_install_error, encode_password, is_protected, make_patch_script, make_unattend, region_error

CRLF = chr(13) + chr(10)
NS = {"u": "urn:schemas-microsoft-com:unattend"}


class UnattendTests(unittest.TestCase):
    def test_xml_parses_and_has_everything(self):
        cfg = {"user": "Pablo & Co", "password": "secret", "computer": "PC1", "edition": "Pro"}
        xml = make_unattend(cfg, PRESETS["Recommended"])
        root = ET.fromstring(xml.encode())
        passes = [s.get("pass") for s in root.findall("u:settings", NS)]
        self.assertEqual(passes, ["windowsPE", "specialize", "oobeSystem"])
        self.assertIn("BypassTPMCheck", xml)
        self.assertIn("winsmith.ps1", xml)
        self.assertIn("Pablo &amp; Co", xml)
        self.assertIn(encode_password("secret"), xml)
        self.assertNotIn("secret<", xml)
        self.assertIn("VK7JG-NPHTM-C97JM-9MPGT-3V66T", xml)

    def test_no_user_no_patches(self):
        xml = make_unattend({}, [])
        ET.fromstring(xml.encode())
        self.assertNotIn("<LocalAccount ", xml)
        self.assertNotIn("HideLocalAccountScreen", xml)
        self.assertNotIn("winsmith.ps1", xml)
        self.assertNotIn("LabConfig", xml)

    def test_password_encoding(self):
        # Same as the old PowerShell ConvertTo-UnattendPassword: base64(UTF-16LE(pw + "Password")).
        self.assertEqual(encode_password("a"), "YQBQAGEAcwBzAHcAbwByAGQA")

    def test_patch_script(self):
        s = make_patch_script(list(PATCHES))
        self.assertIn(r"Reg add 'HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection' /v 'AllowTelemetry' /t REG_DWORD /d 0x0 /f", s)
        self.assertIn(r"Reg add 'HKU\WS_DEFAULT\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' /v 'HideFileExt'", s)
        self.assertIn("/ve /f", s)
        self.assertIn("/t REG_SZ /d '506'", s)
        self.assertIn("Reg delete", s)
        self.assertTrue(s.isascii())
        self.assertEqual(s.count("{"), s.count("}"))

    def test_user_entries_reapplied_at_first_logon(self):
        # Windows overwrites theme/search box/CDM in the new profile, and HKCU\Software\Classes is not in NTUSER.DAT.
        s = make_patch_script(["darkmode", "classicmenu", "tracking"])
        self.assertIn(r"Reg add 'HKU\WS_DEFAULT\Software\Microsoft\Windows\CurrentVersion\RunOnce' /v 'Winsmith'", s)
        user = s[s.index("@'"):s.index("'@")]
        self.assertIn(r"Reg add 'HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' /v 'AppsUseLightTheme'", user)
        self.assertIn(r"Reg add 'HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32' /ve /f", user)
        self.assertNotIn("HKLM", user)
        self.assertNotIn("RunOnce", make_patch_script(["nofaststart"]))  # no user entries, no logon script

    def test_protected_apps_never_removed(self):
        self.assertTrue(is_protected("Microsoft.VCLibs.140.00"))
        self.assertFalse(any(is_protected(a) for a in REMOVE_APPS))
        s = make_patch_script(["bloatapps"])
        self.assertNotIn("WindowsStore", s)

    def test_presets_known_ids(self):
        for ids in PRESETS.values():
            self.assertTrue(set(ids) <= set(PATCHES))

    def test_account_names(self):
        self.assertIsNone(account_error("pablo", "PC-1"))
        self.assertIsNotNone(account_error("Administrator"))
        self.assertIsNotNone(account_error("a/b"))
        self.assertIsNotNone(account_error("pablo", "pablo"))
        self.assertIsNotNone(account_error("pablo", "1234"))
        # A standard user with the setup screens skipped would leave the PC without an admin.
        self.assertIsNotNone(account_error("pablo", admin=False, skip_oobe=True))
        self.assertIsNone(account_error("pablo", admin=False, skip_oobe=False))

    def test_values_are_stripped(self):
        xml = make_unattend({"user": " pablo ", "computer": "   "}, [])
        self.assertIn("<ComputerName>*</ComputerName>", xml)
        self.assertIn("<Name>pablo</Name>", xml)
        self.assertIn("<ComputerName>PC1</ComputerName>", make_unattend({"computer": " PC1 "}, []))

    def test_unattended_off_keeps_only_patches(self):
        xml = make_unattend({"unattended": False, "user": "bob", "edition": "Pro", "computer": "PC1"}, ["hwchecks"])
        ET.fromstring(xml.encode())
        self.assertIn("LabConfig", xml)
        self.assertIn("winsmith.ps1", xml)
        for tag in ("LocalAccount", "ProductKey", "UILanguage", "TimeZone", "ComputerName", "AcceptEula"):
            self.assertNotIn(tag, xml)

    def test_region(self):
        self.assertIsNone(region_error("en-US", "de-DE"))
        self.assertIsNone(region_error("de-DE", "0407:00000407"))
        self.assertIsNotNone(region_error("", "en-US"))
        self.assertIsNotNone(region_error("german", "en-US"))
        self.assertIsNotNone(region_error("en-US", ""))

    def test_auto_install_modes(self):
        off = make_unattend({"edition": "Pro"}, ["hwchecks"])
        self.assertNotIn("WillWipeDisk", off)
        self.assertNotIn("autoinstall.js", off)

        disk0 = make_unattend({"auto_install": "disk0"}, [])
        ET.fromstring(disk0.encode())
        self.assertIn("<DiskID>0</DiskID><WillWipeDisk>true</WillWipeDisk>", disk0)
        self.assertIn("<InstallTo><DiskID>0</DiskID><PartitionID>3</PartitionID></InstallTo>", disk0)

        ssd = make_unattend({"auto_install": "best_ssd", "edition": "Pro"}, ["hwchecks"])
        ET.fromstring(ssd.encode())
        self.assertIn(r'cscript //nologo %d:\sources\autoinstall.js "Windows 11 Pro"', ssd)
        self.assertNotIn("WillWipeDisk", ssd)
        self.assertLess(ssd.index("LabConfig"), ssd.index("autoinstall.js"))  # hardware bypass first

        for mode in ("disk0", "best_ssd"):  # setup answers off: never wipe
            xml = make_unattend({"unattended": False, "auto_install": mode, "edition": "Pro"}, [])
            self.assertNotIn("WillWipeDisk", xml)
            self.assertNotIn("autoinstall.js", xml)

    def test_auto_install_error(self):
        self.assertIsNotNone(auto_install_error({"auto_install": "best_ssd", "edition": ""}))
        self.assertIsNone(auto_install_error({"auto_install": "best_ssd", "edition": "Pro"}))
        self.assertIsNone(auto_install_error({"auto_install": "disk0", "edition": ""}))
        self.assertIsNone(auto_install_error({"auto_install": "best_ssd", "edition": "", "unattended": False}))

    @unittest.skipUnless(sys.platform == "win32", "needs cscript")
    def test_wipe_preview_reads_disks(self):
        from winsmith.iso import wipe_preview
        text = wipe_preview("best_ssd")
        self.assertRegex(text, r"Disk \d+: .+ GB, ")

    @unittest.skipUnless(sys.platform == "win32", "needs cscript")
    def test_autoinstall_picks_disk(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from winsmith.iso import AUTO_JS
        # toDisk(index, model, interface, pnp id, media type, size) like Win32_DiskDrive returns them.
        cases = r"""
        var G = 1073741824, fixed = 'Fixed hard disk media';
        var nvme = toDisk(0, 'Samsung 990 PRO', 'SCSI', 'SCSI\\DISK&VEN_NVME&PROD_SAMSUNG\\1', fixed, 500 * G);
        var nvme2 = toDisk(5, 'WD Black', 'SCSI', 'SCSI\\DISK&VEN_NVME&PROD_WD\\1', fixed, 1000 * G);
        var ssd = toDisk(1, 'Crucial MX500 SSD', 'IDE', 'SCSI\\DISK&VEN_ATA\\1', fixed, 1000 * G);
        var hdd = toDisk(2, 'WDC WD10EZEX', 'IDE', 'SCSI\\DISK&VEN_ATA\\2', fixed, 1000 * G);
        var usb = toDisk(3, 'Samsung T7 NVMe', 'USB', 'USBSTOR\\DISK&VEN_SAMSUNG\\1', 'Removable Media', 500 * G);
        var tiny = toDisk(4, 'NVMe tiny', 'SCSI', 'SCSI\\DISK&VEN_NVME\\2', fixed, 32 * G);
        function show(d) { WScript.Echo(d ? describe(d) : 'none'); }
        show(pickDisk([hdd, ssd, nvme], []));
        show(pickDisk([hdd, ssd], []));
        show(pickDisk([nvme, nvme2], []));
        show(pickDisk([usb, hdd], []));
        show(pickDisk([tiny, hdd], []));
        show(pickDisk([nvme, ssd], [0]));
        show(pickDisk([usb, tiny], []));
        """
        fd, f = tempfile.mkstemp(suffix=".js")
        try:
            with open(fd, "w", encoding="ascii") as fh:
                fh.write("var TESTING = true;\r\n" + AUTO_JS.read_text(encoding="utf-8") + cases)
            out = subprocess.run(["cscript", "//nologo", "//E:jscript", f], capture_output=True, text=True,
                                 timeout=60).stdout.splitlines()
        finally:
            Path(f).unlink(missing_ok=True)
        self.assertEqual(out, [
            "Disk 0: Samsung 990 PRO, 500 GB, NVMe",
            "Disk 1: Crucial MX500 SSD, 1000 GB, SSD",
            "none",  # a tie opens normal setup
            "Disk 2: WDC WD10EZEX, 1000 GB, HDD/other",  # USB is never picked
            "Disk 2: WDC WD10EZEX, 1000 GB, HDD/other",  # under 64 GB is never picked
            "Disk 1: Crucial MX500 SSD, 1000 GB, SSD",  # the install media disk is skipped
            "none",
        ])


class WifiTests(unittest.TestCase):
    CFG = {"wifi_ssid": "Home & Co", "wifi_password": "p<ss>word1"}

    def test_off_without_ssid_and_validation(self):
        self.assertFalse(wifi_on({}))
        self.assertTrue(wifi_on(self.CFG))
        self.assertIsNotNone(wifi_error("x", "short"))
        self.assertIsNone(wifi_error("x", "", "open"))
        self.assertIsNotNone(wifi_error("x" * 33, "password1"))
        self.assertFalse(wifi_on({"wifi_ssid": "x", "wifi_password": "short"}))

    def test_script_escapes_xml(self):
        import base64, re
        s = make_wifi_script(self.CFG)
        xml = base64.b64decode(re.search(r"FromBase64String\('([^']+)'", s).group(1)).decode()
        self.assertIn("Home &amp; Co", xml)
        self.assertIn("p&lt;ss&gt;word1", xml)
        self.assertIn("WPA2PSK", xml)
        self.assertNotIn("word1", s)  # nothing user-typed reaches the script text

    def test_rejects_line_separators_and_unknown_security(self):
        self.assertIsNotNone(wifi_error("x '@", "password1"))
        self.assertIsNotNone(wifi_error("x", "password1"))
        self.assertIsNotNone(wifi_error("x", "password1", "bogus"))
        self.assertIsNotNone(wifi_error("x", "a" * 64, "WPA3"))
        self.assertIsNone(wifi_error("x", "a" * 64, "WPA2"))

    def test_padded_password_agrees_between_unattend_and_build(self):
        cfg = {"wifi_ssid": "x", "wifi_password": "abcdefg "}
        self.assertTrue(wifi_on(cfg))
        self.assertIn("winsmith-wifi.ps1", make_unattend(cfg, []))

    def test_unattend_runs_script_at_specialize_and_final_at_logon(self):
        x = make_unattend(self.CFG, [])
        self.assertEqual(x.count("winsmith-wifi.ps1"), 2)
        self.assertIn("winsmith-wifi.ps1 -Final", x)
        ET.fromstring(x)
        self.assertNotIn("winsmith-wifi", make_unattend({}, []))


class AppsTests(unittest.TestCase):
    def test_app_id_ok(self):
        for good in ("Mozilla.Firefox", "7zip.7zip", "Microsoft.VisualStudioCode", "Git.Git", "A-B.C+D"):
            self.assertTrue(app_id_ok(good), good)
        for bad in ("foo", "x'; rm -rf", "a b.c", "", None, "a..b", ".a.b", "a.b;c"):
            self.assertFalse(app_id_ok(bad), bad)

    def test_apps_script_installs_each_quoted_id_and_waits(self):
        s = make_apps_script(["Mozilla.Firefox", "7zip.7zip"])
        self.assertIn("'Mozilla.Firefox', '7zip.7zip'", s)
        self.assertIn("Test-NetConnection", s)
        self.assertIn("AddMinutes(15)", s)
        self.assertIn("--accept-package-agreements", s)
        self.assertTrue(s.endswith(chr(13) + chr(10)))

    def test_first_logon_command_only_with_valid_apps(self):
        for u in (True, False):
            xml = make_unattend({"unattended": u, "apps": ["Mozilla.Firefox", "x'; rm", "Mozilla.Firefox"]}, [])
            root = ET.fromstring(xml)
            cmds = [e.text for e in root.iter("{urn:schemas-microsoft-com:unattend}CommandLine")]
            self.assertEqual(len(cmds), 1)
            self.assertIn("winsmith-apps.ps1", cmds[0])
        self.assertNotIn("FirstLogonCommands", make_unattend({"apps": []}, []))
        self.assertNotIn("FirstLogonCommands", make_unattend({"apps": ["nope"]}, []))


class IsoNameTests(unittest.TestCase):
    def test_output_name_and_label(self):
        from winsmith import __version__, iso
        name = iso.output_name("/x/Win11_English_x64.iso")
        self.assertRegex(name, rf"Winsmith_Win11_English_x64_v{__version__}_\d{{4}}-\d{{2}}-\d{{2}}\.iso")
        self.assertTrue(iso.is_auto_name(name))
        self.assertTrue(iso.is_auto_name("Winsmith_Win11.iso"))  # name made by older versions
        self.assertFalse(iso.is_auto_name("my-own-name.iso"))
        self.assertLessEqual(len(iso.volume_label()), 32)
        self.assertRegex(iso.volume_label(), r"WINSMITH_[0-9_]+_\d{8}")


if __name__ == "__main__":
    unittest.main()
