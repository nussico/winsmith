import struct
import tempfile
import unittest
from pathlib import Path

from winsmith import wim


def make_wim(names, magic=wim.MAGIC, compressed=False):
    """A minimal WIM: 208 byte header, then the uncompressed UTF-16 XML."""
    xml = "﻿<WIM>" + "".join(f"<IMAGE INDEX=\"{i}\"><NAME>{n}</NAME></IMAGE>" for i, n in enumerate(names, 1)) + "</WIM>"
    raw = xml.encode("utf-16-le")
    head = bytearray(208)
    head[:8] = magic
    head[0x48:0x4F] = len(raw).to_bytes(7, "little")
    head[0x4F] = 0x04 if compressed else 0
    struct.pack_into("<QQ", head, 0x50, 208, len(raw) + (5 if compressed else 0))
    return bytes(head) + raw


class WimTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "install.wim"
            p.write_bytes(data)
            return wim.image_names(p)

    def test_image_names(self):
        self.assertEqual(self.read(make_wim(["Windows 11 Home", "Windows 11 Pro"])), ["Windows 11 Home", "Windows 11 Pro"])

    def test_bad_magic(self):
        with self.assertRaisesRegex(ValueError, "Not a WIM"):
            self.read(make_wim(["x"], magic=b"NOTAWIM\0"))

    def test_compressed_xml_is_refused(self):
        with self.assertRaises(ValueError):
            self.read(make_wim(["x"], compressed=True))

    def test_truncated(self):
        with self.assertRaises(ValueError):
            self.read(make_wim(["Windows 11 Home"])[:230])

    def test_missing_file(self):
        with self.assertRaises(ValueError):
            wim.image_names("does-not-exist.wim")


if __name__ == "__main__":
    unittest.main()
