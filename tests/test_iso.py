import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
