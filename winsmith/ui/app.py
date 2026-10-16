"""Application start-up."""
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from .. import updater
from . import theme
from .window import MainWindow


def app_pixmap(size=64):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 64, size / 64)  # drawn on a 64 grid
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme.LIGHT["accent"]))
    p.drawRoundedRect(QRectF(0, 0, 64, 64), 18, 18)
    p.setBrush(QColor("#FFFFFF"))
    for x in (17, 34):
        for y in (17, 34):
            p.drawRoundedRect(QRectF(x, y, 13, 13), 2.5, 2.5)
    p.end()
    return pm


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        icon.addPixmap(app_pixmap(size))
    return icon


def main():
    if sys.platform == "win32":
        try:  # own taskbar icon instead of python.exe's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Winsmith")
        except Exception:
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Winsmith")
    app.setWindowIcon(app_icon())
    theme.apply(app)
    exe = updater.exe_path()
    if exe:
        updater.cleanup_old(exe)  # the exe the last update replaced
    w = MainWindow()
    w.show()
    w.check_for_updates()
    sys.exit(app.exec())
