"""Slim bar under the app bar: a newer Winsmith exists."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame

from .widgets import button, hbox, label


class UpdateBanner(QFrame):
    def __init__(self, on_update, command):
        super().__init__()
        self.setObjectName("updatebar")
        self.setAttribute(Qt.WA_StyledBackground)
        self.rel = None
        self.command = command
        lay = hbox(self, 10, (20, 6, 20, 6))
        self.text = label("", wrap=True)
        lay.addWidget(self.text, 1)
        self.update_btn = button("Update", lambda: on_update(self.rel), "primary")
        self.copy_btn = button("Copy update command", lambda: QApplication.clipboard().setText(self.command))
        self.later_btn = button("Later", self.hide, "link")
        for b in (self.update_btn, self.copy_btn, self.later_btn):
            lay.addWidget(b)
        self.hide()

    def show_release(self, rel, can_self_update):
        self.rel = rel
        direct = can_self_update and bool(rel.get("asset_url"))  # else fall back to the install command
        self.update_btn.setVisible(direct)
        self.copy_btn.setVisible(not direct)
        self.later_btn.setVisible(True)
        self.set_text(f"Winsmith {rel['version']} is available."
                      + ("" if direct else f" Update with: {self.command}"))
        self.update_btn.setEnabled(True)
        self.show()

    def set_text(self, text):
        self.text.setText(text)

    def busy(self, text):
        """While downloading: no buttons to press."""
        self.set_text(text)
        self.update_btn.setEnabled(False)
        self.later_btn.setVisible(False)

