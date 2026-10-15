"""Build dist/Winsmith.exe with Nuitka: one file, no Python needed on the target PC.

    python -m pip install "nuitka>=4.4"   # 4.3 builds an exe that crashes on start with Python 3.14 + PySide6
    python build_exe.py            # dist/Winsmith.exe
    python build_exe.py --debug    # build/main.dist/Winsmith.exe: folder build with a console for tracebacks

Needs a C compiler: Visual Studio Build Tools with the "Desktop development with C++" workload.
"""
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
SIZES = (16, 24, 32, 48, 64, 256)


def write_ico(path):
    """Multi-size .ico from the app's own icon (PNG entries, Vista and newer)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtWidgets import QApplication
    from winsmith.ui.app import app_pixmap

    app = QApplication.instance() or QApplication([])  # QPixmap needs one
    images = []
    for size in SIZES:
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        app_pixmap(size).save(buf, "PNG")
        images.append((size, bytes(buf.data())))
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    entries, data = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size  # 0 means 256
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    path.write_bytes(head + entries + data)
    del app


def main():
    if sys.platform != "win32":
        sys.exit("Build the .exe on Windows.")
    sys.path.insert(0, str(ROOT))
    from winsmith import __version__

    BUILD.mkdir(exist_ok=True)
    ico = BUILD / "winsmith.ico"
    write_ico(ico)
    debug = "--debug" in sys.argv
    if debug:
        mode = ["--standalone", "--windows-console-mode=force"]
    else:
        mode = ["--onefile", "--windows-console-mode=disable",
                # Unpack once per version instead of on every start: faster launches.
                "--onefile-tempdir-spec={CACHE_DIR}/Winsmith/" + __version__]
    cmd = [
        sys.executable, "-m", "nuitka", str(ROOT / "main.py"), *mode,
        "--enable-plugin=pyside6",
        # Copied into the ISO for the Best SSD automatic install.
        f"--include-data-files={ROOT / 'winsmith' / 'autoinstall.js'}=winsmith/autoinstall.js",
        f"--windows-icon-from-ico={ico}",
        "--product-name=Winsmith",
        "--company-name=Winsmith",
        "--file-description=Build your own Windows 11 ISO",
        f"--product-version={__version__}",
        f"--file-version={__version__}",
        "--msvc=latest",
        "--assume-yes-for-downloads",
        f"--output-dir={BUILD}",
        "--output-filename=Winsmith.exe",
    ]
    subprocess.run(cmd, check=True)
    if debug:
        print(f"\nDone: {BUILD / 'main.dist' / 'Winsmith.exe'}")
        return
    DIST.mkdir(exist_ok=True)
    exe = DIST / "Winsmith.exe"
    (BUILD / "Winsmith.exe").replace(exe)
    print(f"\nDone: {exe} ({exe.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
