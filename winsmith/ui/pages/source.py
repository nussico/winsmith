"""Step 1: pick the Windows ISO."""
from pathlib import Path

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QLineEdit

from ... import iso
from ..page import Page
from ..widgets import DiscIcon, DropZone, Field, button, hbox, label, vbox

DOWNLOAD_URL = "https://www.microsoft.com/software-download/windows11"


class InfoSignals(QObject):
    """Reading the ISO runs in a thread; this hands the answer to the UI thread."""
    done = Signal(str, object, object)  # ISO path, architecture, image names


class SourcePage(Page):
    def __init__(self, win):
        super().__init__("Choose a Windows 11 ISO", "Winsmith reads it and writes a new one. Your file is never changed.")
        self.win = win
        self.info = {}  # ISO path -> (arch, image names) once read
        self.reading = None
        self.sig = InfoSignals()
        self.sig.done.connect(self._got_info)

        self.drop = DropZone("Drop a Windows 11 ISO here", "or click to browse")
        self.drop.clicked.connect(self.browse)
        self.drop.dropped.connect(self.set_path)
        self.body.addWidget(self.drop)

        self.file = QFrame()
        self.file.setObjectName("file")
        fl = hbox(self.file, 14, (18, 16, 18, 16))
        fl.addWidget(DiscIcon(40, ok=True), 0, Qt.AlignVCenter)
        info = vbox(spacing=2)
        info.addWidget(label("✓  Ready", "ok"))
        self.file_name = label("", "strong", wrap=True)
        self.file_meta = label("", "small", wrap=True)
        info.addWidget(self.file_name)
        info.addWidget(self.file_meta)
        fl.addLayout(info, 1)
        fl.addWidget(button("Change…", self.browse), 0, Qt.AlignVCenter)
        self.body.addWidget(self.file)

        self.path = QLineEdit(win.s["iso"])
        self.path.setPlaceholderText("C:\\Downloads\\Win11_English_x64.iso")
        self.path.textChanged.connect(self._typed)
        self.field = Field("Or paste the path", self.path)
        self.body.addWidget(self.field)

        self.download = label(f'Don\'t have one? <a href="{DOWNLOAD_URL}">Download Windows 11 from Microsoft</a>',
                              "muted", wrap=True)
        self.download.setOpenExternalLinks(True)
        self.download.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.body.addWidget(self.download)

        self.next_btn = button("Next", lambda: win.show_page("Patches"), "primary")
        self.add_right(self.next_btn)

    def _typed(self, raw):
        clean = raw.strip().strip('"')
        if raw != clean:  # pasted from Explorer's "Copy as path"
            self.path.setText(clean)  # calls back here with the clean value
            return
        self.win.s["iso"] = raw
        out = self.win.s["output"]
        if Path(raw).is_file():  # keep a name the user typed, and the folder they chose
            if not out:
                self.win.pages["Build"].set_output(iso.default_output(raw))
            elif iso.is_auto_name(out):
                self.win.pages["Build"].set_output(str(Path(out).with_name(iso.output_name(raw))))
        self.refresh()

    def set_path(self, p):
        self.path.setText(str(Path(p)))  # _typed names the output

    def browse(self):
        start = str(Path(self.win.s["iso"]).parent) if self.win.s["iso"] else ""
        p, _ = QFileDialog.getOpenFileName(self, "Windows 11 ISO", start, "ISO image (*.iso);;All files (*)")
        if p:
            self.set_path(p)

    def _info_text(self, raw):
        arch, names = self.info.get(raw, (None, None))
        if arch is None:
            return ""
        eds = iso.editions_in(names or [])
        return f"\n{'ARM64' if arch == 'arm64' else 'x64'}" + (f"  ·  {', '.join(eds)}" if eds else "")

    def _read_info(self, raw):
        """Which editions and architecture the ISO holds (Windows only). Read once per file, in a thread."""
        if raw in self.info:
            self.win.pages["Setup"].set_editions(iso.editions_in(self.info[raw][1] or []) or None)
            return
        self.win.pages["Setup"].set_editions(None)  # until this ISO has been read
        if self.reading == raw or not iso.IS_WINDOWS:
            return
        self.reading = raw
        threading.Thread(target=lambda: self.sig.done.emit(raw, *iso.read_info(raw)), daemon=True).start()

    def _got_info(self, raw, arch, names):
        if self.reading == raw:
            self.reading = None
        self.info[raw] = (arch, names)
        if raw == self.win.s["iso"]:
            self.refresh()

    def ok(self):
        raw = self.win.s["iso"]
        return bool(raw) and Path(raw).is_file()

    def refresh(self):
        raw = self.win.s["iso"]
        ok = self.ok()
        self.drop.setVisible(not ok)
        self.file.setVisible(ok)
        if ok:
            p = Path(raw)
            self.file_name.setText(p.name)
            self.file_meta.setText(f"{p.stat().st_size / 2**30:.1f} GB  ·  {p.parent}" + self._info_text(raw))
            self._read_info(raw)
        else:
            self.win.pages["Setup"].set_editions(None)
        self.download.setVisible(not raw)
        self.field.set_error("File not found." if raw and not ok else None)
        self.win.update_steps()
