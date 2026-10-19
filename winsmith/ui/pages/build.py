"""Step 4: check everything, then write the new ISO."""
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QApplication, QFileDialog, QGraphicsOpacityEffect, QGridLayout, QLineEdit, QMessageBox,
                               QPlainTextEdit, QWidget)

from ... import iso
from ...unattend import auto_mode
from ..page import Page
from ..theme import T
from ..widgets import Field, ProgressBar, Section, animation, button, hbox, label, set_prop, vbox

SUMMARY = [("Windows ISO", "Source"), ("Tweaks", "Patches"), ("User", "Setup"), ("Edition", "Setup"),
           ("Language", "Setup")]


class BuildSignals(QObject):
    """The build runs in a thread; these hand its progress to the UI thread."""
    log = Signal(str)
    step = Signal(int, int, str)
    done = Signal(object)
    installed = Signal(object)


class BuildPage(Page):
    def __init__(self, win):
        super().__init__("Build your ISO", "Takes a few minutes. Building needs no admin rights.")
        self.win = win
        self.building = self.installing = False
        self.out = self.cancel = self.job = None
        self.log_open = False
        self.floor = self.target = 0.0
        self.sig = BuildSignals()
        self.sig.log.connect(lambda m: self._log(m))
        self.sig.step.connect(self._on_step)
        self.sig.done.connect(self._finish)
        self.sig.installed.connect(self._installed)
        self.ticker = QTimer(self)
        self.ticker.setInterval(33)
        self.ticker.timeout.connect(self._tick)

        self.tools = Section("Install a missing tool first", warn=True)
        self.tools_body = None
        self.body.addWidget(self.tools)

        out = Section("Save as")
        row = hbox(spacing=10)
        self.out_edit = QLineEdit(win.s["output"])
        self.out_edit.setPlaceholderText("Where the new ISO goes")
        self.out_edit.textChanged.connect(lambda t: win.s.__setitem__("output", t))
        self.f_out = Field("New ISO file", self.out_edit)
        row.addWidget(self.f_out, 1)
        browse = button("Browse…", self._browse)
        row.addWidget(browse, 0, Qt.AlignTop)
        browse.setStyleSheet("margin-top: 27px;")  # line up with the input, not its label
        out.body.addLayout(row)
        self.body.addWidget(out)

        summ = Section("Summary")
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1)
        self.summary = {}
        for i, (k, page) in enumerate(SUMMARY):
            g.addWidget(label(k, "muted"), i, 0, Qt.AlignTop)
            self.summary[k] = label("", wrap=True)
            g.addWidget(self.summary[k], i, 1)
            if k not in ("Edition", "Language"):
                g.addWidget(button("Edit", lambda _=False, p=page: win.show_page(p), "link"), i, 2, Qt.AlignTop)
        summ.body.addLayout(g)
        self.body.addWidget(summ)

        prog = Section("Progress")
        self.status_box = QWidget()
        sb = vbox(self.status_box, 2)
        self.status = label("Ready when you are", "big")
        self.status_sub = label("Nothing is written until you press Build ISO.", "small", wrap=True)
        self.status_sub.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sb.addWidget(self.status)
        sb.addWidget(self.status_sub)
        self.status_fade = QGraphicsOpacityEffect(self.status_box)
        self.status_fade.setEnabled(False)
        self.status_box.setGraphicsEffect(self.status_fade)
        self.status_anim = animation(self, 300, self.status_fade.setOpacity)
        self.status_anim.finished.connect(self._status_done)
        prog.body.addWidget(self.status_box)
        prog.body.addSpacing(14)
        self.pbar = ProgressBar()
        prog.body.addWidget(self.pbar)
        prog.body.addSpacing(10)
        self.details_btn = button("Show details", self._toggle_log, "link")
        prog.body.addWidget(self.details_btn, 0, Qt.AlignLeft)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(0)
        self.log_box.hide()
        self.log_anim = animation(self, 220, lambda h: self.log_box.setMaximumHeight(int(h)), 0, 260)
        self.log_anim.finished.connect(self._log_done)
        prog.body.addSpacing(6)
        prog.body.addWidget(self.log_box)
        self.body.addWidget(prog)

        self.add_left(button("Back", lambda: win.show_page("Setup"), "ghost"))
        self.open_btn = button("Show in folder", self._open_folder)
        self.open_btn.hide()
        self.add_right(self.open_btn)
        self.build_btn = button("Build ISO", self.build, "primary", big=True)
        self.add_right(self.build_btn)

    def set_output(self, path):
        self.out_edit.setText(path)

    # ---------- summary and tools ----------
    def refresh(self):
        w, s = self.win, self.win.s
        src = s["iso"]
        self.summary["Windows ISO"].setText(Path(src).name if src else "Not picked yet")
        set_prop(self.summary["Windows ISO"], "role", None if w.pages["Source"].ok() else "error")
        ids = w.selected()
        match = w.pages["Patches"].matching()
        self.summary["Tweaks"].setText(f"{len(ids)} on" + (f" ({match})" if match else "") if ids else "None")
        on, ask = s["unattended"], "Asked during setup"
        self.summary["User"].setText(on and s["user"].strip() or ask)
        self.summary["Edition"].setText(on and s["edition"] or ask)
        self.summary["Language"].setText(f"{s['language']}, keyboard {s['keyboard']}, {s['timezone']}" if on else ask)
        self._refresh_tools()

    def _refresh_tools(self):
        if self.tools_body is not None:
            self.tools.body.removeWidget(self.tools_body)
            self.tools_body.deleteLater()
            self.tools_body = None
        missing = iso.missing_tools()
        if missing:
            self.tools_body = QWidget()
            lay = vbox(self.tools_body, 8)
            for tool, hint in missing:
                lay.addWidget(label(f"{tool} is needed to write the ISO. Install it with:", wrap=True))
                row = hbox(spacing=10)
                cmd = label(hint, wrap=True)
                cmd.setObjectName("cmd")
                cmd.setTextInteractionFlags(Qt.TextSelectableByMouse)
                row.addWidget(cmd, 1)
                first = hint.split("  (")[0].split("   /   ")[0]
                row.addWidget(button("Copy", lambda _=False, c=first: QApplication.clipboard().setText(c)), 0,
                              Qt.AlignTop)
                lay.addLayout(row)
                if tool == "oscdimg" and iso.can_install_oscdimg():
                    inst = button("Installing… confirm the Windows prompt" if self.installing else "Install it for me",
                                  self._install_tool, "primary")
                    inst.setEnabled(not self.installing)
                    lay.addWidget(inst, 0, Qt.AlignLeft)
            lay.addWidget(button("Check again", self.refresh, "link"), 0, Qt.AlignLeft)
            self.tools.body.addWidget(self.tools_body)
        self.tools.setVisible(bool(missing))
        if not self.building:
            self.build_btn.setEnabled(not missing)

    def _install_tool(self):
        if self.installing or self.building:
            return
        self.installing = True
        self._refresh_tools()
        self._set_status("Installing oscdimg…", "Windows asks for admin rights for the ADK installer. Takes a few minutes.")
        threading.Thread(target=self._install_thread, daemon=True).start()

    def _install_thread(self):
        try:
            iso.install_oscdimg(self.sig.log.emit)
            self.sig.installed.emit(None)
        except Exception as e:  # show any failure in the UI instead of crashing it
            self.sig.installed.emit(str(e))

    def _installed(self, err):
        self.installing = False
        self.refresh()
        if self.building:
            return
        if err:
            self._set_status("oscdimg not installed", err, "danger")
        elif iso.missing_tools():
            self._set_status("oscdimg not found", "The install finished but oscdimg is still missing.", "danger")
        else:
            self._set_status("oscdimg installed", "Ready to build.", "success")

    def _browse(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save ISO as", self.win.s["output"], "ISO image (*.iso)")
        if p:
            if not p.lower().endswith(".iso"):
                p += ".iso"
            self.out_edit.setText(str(Path(p)))

    # ---------- status ----------
    def _set_status(self, title, sub, color_key="text"):
        self.status.setText(title)
        self.status.setStyleSheet(f"color: {T[color_key]};")
        self.status_sub.setText(sub)
        self.status_fade.setOpacity(0)
        self.status_fade.setEnabled(True)
        self.status_anim.stop()
        self.status_anim.start()

    def _toggle_log(self):
        self.log_open = not self.log_open
        self.details_btn.setText("Hide details" if self.log_open else "Show details")
        self.log_anim.stop()
        self.log_anim.setStartValue(float(self.log_box.maximumHeight()))
        self.log_anim.setEndValue(260.0 if self.log_open else 0.0)
        if self.log_open:
            self.log_box.show()
            self._log_to_end()
        self.log_anim.start()

    def _status_done(self):
        self.status_fade.setEnabled(False)

    def _log_done(self):
        if not self.log_open:
            self.log_box.hide()

    def _log(self, text, color_key="muted"):
        cur = self.log_box.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(T[color_key]))
        cur.insertText(text + "\n", fmt)
        self._log_to_end()

    def _log_to_end(self):
        bar = self.log_box.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ---------- build ----------
    def build(self):
        out = self.win.s["output"]
        if out and iso.is_auto_name(out):  # an automatic name gets today's date, not the day it was picked
            self.set_output(str(Path(out).with_name(iso.output_name(self.win.s["iso"]))))  # same folder as chosen
        problem = self.win.check()
        if problem:
            msg, page, field = problem
            self._set_status("Can't build yet", msg, "danger")
            self.pbar.set(0, 200)
            self.pbar.set_color("danger")
            if page != self.win.current:  # let the message register, then take the user there
                QTimer.singleShot(900, lambda: (self.win.show_page(page), QTimer.singleShot(300, field.shake)))
            else:
                field.shake()
            return
        if not self.confirm_wipe():
            return
        self.win.save_config()
        self.building = True
        self.build_btn.setEnabled(False)
        self.build_btn.setText("Building…")
        self.open_btn.hide()
        self.log_box.clear()
        self.pbar.set(0, 0)
        self.pbar.set_color("accent")
        self.pbar.shimmer(True)
        self.floor = self.target = 0
        self._set_status("Starting…", "")
        self.out = Path(self.win.s["output"]).resolve()
        self.cancel = threading.Event()
        args = (self.win.s["iso"], self.out, self.win.settings(), self.win.selected())
        self.job = threading.Thread(target=self._thread, args=args, daemon=True)
        self.job.start()
        self.ticker.start()

    def confirm_wipe(self):
        mode = auto_mode(self.win.s)
        if mode == "off":
            return True
        what = ("DISK 0 of any PC booted from this ISO will be ERASED without asking." if mode == "disk0" else
                "Any PC booted from this ISO with one clear best disk will have that disk ERASED "
                "after a 10 second countdown.")
        box = QMessageBox(QMessageBox.Warning, "Winsmith", f"Automatic install is ON.\n\n{what}",
                          QMessageBox.Yes | QMessageBox.No, self)
        box.setInformativeText(iso.wipe_preview(mode) + "\n\nBuild anyway?")
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def _thread(self, src, out, settings, ids):
        try:
            iso.build(src, out, settings, ids, self.sig.log.emit, self.sig.step.emit, self.cancel)
            self.sig.done.emit(None)
        except Exception as e:  # show any failure in the UI instead of crashing it
            self.sig.done.emit(str(e))

    def _on_step(self, i, n, text):
        self.floor = (i - 1) / n * 100
        self.target = i / n * 100 - 2
        self._set_status(text, f"Step {i} of {n}")

    def _tick(self):
        """Ease to the start of the current step, then creep towards its end so the bar never looks frozen."""
        v = self.pbar.value
        if v < self.floor:
            v += (self.floor - v) * 0.15
        elif v < self.target:
            v += max(0.01, (self.target - v) / 900)
        self.pbar.set(v, 0)

    def _finish(self, err):
        self.building = False
        self.ticker.stop()
        self.pbar.shimmer(False)
        self.build_btn.setEnabled(not iso.missing_tools())
        self.build_btn.setText("Build ISO")
        if err:
            self._log(f"ERROR: {err}", "danger")
            self.pbar.set_color("danger")
            self._set_status("Build failed", err, "danger")
            if not self.log_open:
                self._toggle_log()
        else:
            out = self.out
            self._log("ISO ready.", "success")
            self.pbar.set(100, 500)
            self.pbar.set_color("success")
            size = f" ({out.stat().st_size / 2**30:.1f} GB)" if out.exists() else ""
            self._set_status("✓  Your ISO is ready",
                             f"{out}{size}\nWrite it to a USB stick with Rufus or Ventoy, or boot it in a VM.",
                             "success")
            self.open_btn.show()

    def _open_folder(self):
        out = self.out
        if iso.IS_WINDOWS:
            subprocess.Popen(["explorer", "/select,", str(out)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(out)])
        else:
            subprocess.Popen(["xdg-open", str(out.parent)])

