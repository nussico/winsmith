"""Main window: app bar with the step indicator, the four pages, settings and profiles."""
import json
import os
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMessageBox, QStackedWidget, QWidget

from .. import __version__, profiles, updater
from ..patches import PATCHES, PRESETS, resolve
from ..unattend import DEFAULTS, auto_mode
from .pages.build import BuildPage
from .pages.patches import PatchesPage
from .pages.setup import SetupPage
from .pages.source import SourcePage
from .stepper import Stepper
from .update_banner import UpdateBanner
from .widgets import Logo, hbox, label, vbox


def _config_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Winsmith"


CONFIG = _config_dir() / "config.json"
OLD_CONFIG = Path(__file__).resolve().parent.parent.parent / "config.json"  # where versions before 0.2 kept it
SECRET_KEYS = {"password"}  # never written to config.json
UI_DEFAULTS = {**DEFAULTS, "unattended": False, "user": "User"}  # fresh install: Setup asks as usual; "User" is ready when switched on
DEFAULT_PRESET = "Basic"
PAGES = ["Source", "Patches", "Setup", "Build"]
NARROW = 640


class UpdateSignals(QObject):
    """The update check and download run in threads; these hand the result to the UI thread."""
    found = Signal(object)
    progress = Signal(float)
    done = Signal(object)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setWindowTitle("Winsmith")
        self.resize(1000, 720)
        self.setMinimumSize(480, 540)

        self.ready = False
        self.current = None
        self.profile_dir = CONFIG.parent / "profiles"
        cfg = self._load_config()
        self.s = {k: type(d)(cfg.get(k, d)) for k, d in {**UI_DEFAULTS, "iso": "", "output": ""}.items()}
        self.s["password"] = ""
        self.patches = set(resolve(cfg.get("patches", PRESETS[DEFAULT_PRESET])))
        self.last_update_check = float(cfg.get("last_update_check", 0) or 0)
        self.upd = UpdateSignals()
        self.upd.found.connect(self._show_update)
        self.upd.progress.connect(lambda f: self.banner.busy(f"Downloading update… {int(f * 100)}%"))
        self.upd.done.connect(self._update_done)

        root = vbox(self)
        bar = QWidget()
        bar.setObjectName("appbar")
        bar.setAttribute(Qt.WA_StyledBackground)
        bl = hbox(bar, 0, (20, 4, 20, 4))
        bl.addWidget(Logo())
        bl.addSpacing(10)
        self.brand = label("Winsmith")
        self.brand.setObjectName("brand")
        bl.addWidget(self.brand)
        self.brand_gap = 32
        bl.addSpacing(self.brand_gap)
        self.stepper = Stepper(PAGES)
        self.stepper.selected.connect(self.show_page)
        bl.addWidget(self.stepper, 1)
        bl.addSpacing(24)
        self.version = label(f"v{__version__}")
        self.version.setObjectName("version")
        bl.addWidget(self.version)
        root.addWidget(bar)
        self.banner = UpdateBanner(self.start_update, updater.UPDATE_COMMAND)
        root.addWidget(self.banner)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.pages = {}
        for name, cls in zip(PAGES, (SourcePage, PatchesPage, SetupPage, BuildPage)):
            self.pages[name] = cls(self)
            self.stack.addWidget(self.pages[name])
        self.ready = True
        self.pages["Source"].refresh()
        self.pages["Patches"].refresh()
        self.pages["Setup"].refresh()

        QShortcut(QKeySequence("Ctrl+Tab"), self, lambda: self._step(1))
        for seq in ("Ctrl+Shift+Tab", "Ctrl+Shift+Backtab"):
            QShortcut(QKeySequence(seq), self, lambda: self._step(-1))
        for i, name in enumerate(PAGES, 1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda n=name: self.show_page(n))
        self.show_page("Source")

    # ---------- updates ----------
    def check_for_updates(self, force=False):
        """Looks for a newer release in the background, at most once a day."""
        if not force and not updater.due(self.last_update_check):
            return
        self.last_update_check = time.time()

        def work():
            rel = updater.check(__version__)
            if rel:
                self.upd.found.emit(rel)

        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, rel):
        self.banner.show_release(rel, updater.is_frozen())

    def start_update(self, rel):
        build = self.pages["Build"]
        if build.building or build.installing:
            self.banner.set_text("Finish the current build or install first, then update.")
            return
        exe = updater.exe_path()
        if exe is None or not rel or not rel.get("asset_url"):
            return
        self.banner.busy("Downloading update… 0%")

        def work():
            new = exe.with_name(exe.stem + ".new" + exe.suffix)
            try:
                updater.download(rel["asset_url"], new, rel["size"], self.upd.progress.emit)
                updater.apply(new, exe)
                updater.relaunch(exe)
                self.upd.done.emit(None)
            except Exception as e:  # show any failure in the banner, keep the current version running
                new.unlink(missing_ok=True)
                self.upd.done.emit(str(e) or type(e).__name__)

        threading.Thread(target=work, daemon=True).start()

    def _update_done(self, err):
        if err:
            self.banner.show_release(self.banner.rel, True)
            self.banner.set_text(f"Update failed: {err}")
            return
        self.save_config()
        QApplication.quit()

    # ---------- navigation ----------
    def show_page(self, name):
        if name == self.current:
            return
        self.current = name
        self.stepper.select(name)
        if name == "Build":
            self.pages["Build"].refresh()
        self.stack.setCurrentWidget(self.pages[name])
        self.pages[name].enter()

    def _step(self, d):
        self.show_page(PAGES[(PAGES.index(self.current) + d) % len(PAGES)])

    def resizeEvent(self, e):
        super().resizeEvent(e)
        wide = e.size().width() >= NARROW
        self.brand.setVisible(wide)
        self.version.setVisible(wide)

    def update_steps(self):
        """Status line under each step."""
        if not self.ready:
            return
        src = self.pages["Source"]
        if src.ok():
            self.stepper.set_status("Source", "Ready", "ok")
        else:
            self.stepper.set_status("Source", "File not found" if self.s["iso"] else "Pick an ISO",
                                    "error" if self.s["iso"] else "")
        pat = self.pages["Patches"]
        pat.sync_chip()
        match = pat.matching()
        self.stepper.set_status("Patches", match or f"{len(self.patches)} on", "info")
        wipe = auto_mode(self.s)
        if self.pages["Setup"].validate():
            self.stepper.set_status("Setup", "Needs a fix", "error")
        elif wipe != "off":
            self.stepper.set_status("Setup", "Wipes best SSD" if wipe == "best_ssd" else "Wipes disk 0", "error")
        else:
            self.stepper.set_status("Setup", "Automatic" if self.s["unattended"] else "Asked during setup", "info")

    # ---------- state ----------
    def selected(self):
        return [pid for pid in PATCHES if pid in self.patches]  # catalog order

    def settings(self):
        return {k: v for k, v in self.s.items() if k not in ("iso", "output")}

    def current_profile(self, name):
        return profiles.to_profile(name, self.s, self.selected())

    def apply_profile(self, prof):
        setup, ids = profiles.from_profile(prof)
        self.s.update(setup)
        self.pages["Setup"].load()
        self.pages["Patches"].set_patches(set(ids))

    def check(self):
        """Returns (problem, page, field to point at) or None."""
        src, build = self.pages["Source"], self.pages["Build"]
        if not src.ok():
            return "Pick a Windows 11 ISO first.", "Source", src.field
        if not self.s["output"].strip():
            return "Choose where to save the new ISO.", "Build", build.f_out
        if Path(self.s["output"]).resolve() == Path(self.s["iso"]).resolve():
            return "The new ISO must be a different file than the original.", "Build", build.f_out
        problem = self.pages["Setup"].validate()
        if problem:
            return f"Setup: {problem[0]}", "Setup", problem[1]
        return None

    def _load_config(self):
        for path in (CONFIG, OLD_CONFIG):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        return {}

    def save_config(self):
        data = {k: v for k, v in self.s.items() if k not in SECRET_KEYS}
        data["patches"] = self.selected()
        data["last_update_check"] = self.last_update_check
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def closeEvent(self, e):
        build = self.pages["Build"]
        if build.building:
            if QMessageBox.question(self, "Winsmith", "A build is running. Stop it and quit?") != QMessageBox.Yes:
                e.ignore()
                return
            # Let the build stop and clean up (temp folder, mounted ISO) before the process ends.
            build.cancel.set()
            self.hide()
            self.save_config()
            self._quit_when_stopped()
            e.ignore()
            return
        self.save_config()
        e.accept()

    def _quit_when_stopped(self):
        if self.pages["Build"].job.is_alive():
            QTimer.singleShot(200, self._quit_when_stopped)
        else:
            QApplication.quit()
