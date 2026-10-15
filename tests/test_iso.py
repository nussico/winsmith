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


if __name__ == "__main__":
    unittest.main()
