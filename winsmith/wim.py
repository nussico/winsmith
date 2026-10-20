"""Read the image names (editions) from a Windows install.wim / install.esd / install.swm without any tool.

A WIM starts with a 208 byte header. The XML resource header at offset 0x48 is 24 bytes: 1 flag byte + 7 bytes
compressed size, 8 bytes offset, 8 bytes original size. The XML itself is stored uncompressed as UTF-16LE.
"""
import re
import struct

MAGIC = b"MSWIM\x00\x00\x00"
MAX_XML = 16 * 2**20


def image_names(path):
    """The <NAME> of each image, in order. Raises ValueError when the file is not a readable WIM."""
    try:
        with open(path, "rb") as f:
            head = f.read(208)
            if len(head) < 208 or not head.startswith(MAGIC):
                raise ValueError("Not a WIM file.")
            size = int.from_bytes(head[0x48:0x4F], "little")
            offset, original = struct.unpack_from("<QQ", head, 0x50)
            if not 0 < size <= MAX_XML or size != original:
                raise ValueError("The image list is compressed or missing.")
            f.seek(offset)
            raw = f.read(size)
    except OSError as e:
        raise ValueError(f"Could not read the image: {e.strerror or e}") from e
    if len(raw) != size:
        raise ValueError("The image list is cut off.")
    text = raw.decode("utf-16-le", errors="replace").lstrip("﻿")
    names = []
    for image in re.findall(r"<IMAGE\b.*?</IMAGE>", text, re.DOTALL):
        m = re.search(r"<NAME>(.*?)</NAME>", image, re.DOTALL)
        if m:
            names.append(m.group(1).strip())
    return names
