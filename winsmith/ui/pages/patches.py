"""Step 2: pick a preset or saved profile as a card, then fine-tune single patches if you want."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox, QWidget

from ... import profiles
from ...patches import PATCHES, PRESETS
from ..page import NARROW, Page
from ..widgets import ChoiceCard, ResponsiveGrid, Section, ToggleRow, button, hbox, label, set_prop, vbox

ABOUT = {
    "Basic": "Only what is needed to install anywhere: no hardware checks, local account, no BitLocker.",
    "Recommended": "Basic plus less bloat, less tracking, no Copilot or ads. A good choice for most PCs.",
    "Everything": "Every patch, including the taste-based ones like dark mode and a left taskbar.",
}
PROFILE_ABOUT = "Your saved profile: its tweaks and Setup answers."


class PatchesPage(Page):
    def __init__(self, win):
        super().__init__("Pick your tweaks", "They run once while Windows installs. The Windows image itself is not modified.")
        self.win = win
        self.bulk = False
        self.user_profiles = []
        self.cards = {}
        bar = hbox(spacing=8)
        self.count = label("", "muted")
        bar.addWidget(self.count, 1)
        self.menu_btn = button("Profiles ▾", kind="ghost")
        self.menu_btn.setAccessibleName("Profiles")
        self.menu = QMenu(self)
        self.menu.aboutToShow.connect(self._fill_menu)
        self.menu_btn.setMenu(self.menu)
        bar.addWidget(self.menu_btn)
        self.body.addLayout(bar)

        self.grid = ResponsiveGrid(NARROW - 40, 3, Qt.Alignment())
        self.grid.grid.setHorizontalSpacing(12)
        self.grid.grid.setVerticalSpacing(12)
        self.body.addWidget(self.grid)

        self.custom = QWidget()
        cl = hbox(self.custom, 8)
        self.custom_text = label("", "accent")
        cl.addWidget(self.custom_text)
        cl.addWidget(button("Save as profile…", self.save_dialog, "link"))
        cl.addStretch(1)
        self.body.addWidget(self.custom)

        self.customize = button("Customize tweaks…", self.toggle_list)
        self.body.addWidget(self.customize, 0, Qt.AlignLeft)

        groups = {}
        for pid, p in PATCHES.items():
            groups.setdefault(p["group"], []).append(pid)
        self.list = QWidget()
        lay = vbox(self.list, 16)
        self.groups, self.rows = [], {}
        for g, ids in groups.items():
            box = Section(g)
            box.body.setSpacing(14)
            for pid in ids:
                t = ToggleRow(PATCHES[pid]["label"], PATCHES[pid]["desc"], pid in win.patches)
                t.toggled.connect(lambda on, pid=pid: self._set(pid, on))
                box.body.addWidget(t)
                self.rows[pid] = t
            self.groups.append((box, ids))
            lay.addWidget(box)
        self.list.hide()
        self.body.addWidget(self.list)

        self.add_left(button("Back", lambda: win.show_page("Source"), "ghost"))
        self.add_right(button("Next", lambda: win.show_page("Setup"), "primary"))
        self.reload_profiles()

    def toggle_list(self):
        self.show_list(self.list.isHidden())

    def show_list(self, on):
        self.list.setVisible(on)
        self.customize.setText("Hide tweaks" if on else "Customize tweaks…")

    # ---------- selection ----------
    def _set(self, pid, on):
        (self.win.patches.add if on else self.win.patches.discard)(pid)
        if not self.bulk:
            self.refresh()

    def set_patches(self, ids):
        self.bulk = True  # refresh once at the end, not once per switch
        try:
            for pid, row in self.rows.items():
                row.setChecked(pid in ids)
        finally:
            self.bulk = False
        self.refresh()

    def apply_choice(self, name):
        if name in PRESETS:
            self.set_patches(set(PRESETS[name]))
            return
        prof = next((p for p in self.user_profiles if p["name"] == name), None)
        if prof:
            self.win.apply_profile(prof)

    def matching(self):
        """Name of the card that matches the current state, or None."""
        sel = self.win.patches
        for p in self.user_profiles:  # a profile also has to match the Setup answers
            setup, ids = profiles.from_profile(p)
            if set(ids) == sel and all(self.win.s.get(k) == v for k, v in setup.items()):
                return p["name"]
        return next((n for n, ids in PRESETS.items() if set(ids) == sel), None)

    def refresh(self):
        sel = self.win.patches
        self.count.setText(f"{len(sel)} of {len(PATCHES)} on")
        for box, ids in self.groups:
            n = sum(i in sel for i in ids)
            box.aside.setText(f"{n} of {len(ids)} on")
            set_prop(box.aside, "role", "accent" if n else "small")
        self.win.update_steps()  # also calls sync_chip()

    def sync_chip(self):
        """Select the card that matches the current state; none (and the custom line) when it is a custom mix."""
        match = self.matching()
        for n, card in self.cards.items():
            card.set_selected(n == match)
        self.custom.setVisible(match is None)
        self.custom_text.setText(f"Custom selection · {len(self.win.patches)} tweaks —")
        if match is None and self.list.isHidden():
            self.show_list(True)

    def current(self):
        return next((n for n, c in self.cards.items() if c.property("selected")), None)

    # ---------- profiles ----------
    def reload_profiles(self):
        self.user_profiles = profiles.list_profiles(self.win.profile_dir)
        self.grid.clear()
        self.cards = {}
        for n, ids in PRESETS.items():
            self._add_card(n, f"{len(ids)} tweaks", ABOUT.get(n, ""))
        for p in self.user_profiles:
            if p["name"] not in PRESETS:
                self._add_card(p["name"], f"{len(profiles.from_profile(p)[1])} tweaks · Setup answers", PROFILE_ABOUT)
        self.refresh()

    def _add_card(self, name, meta, desc):
        card = ChoiceCard(name, meta, desc)
        card.clicked.connect(lambda n=name: self.apply_choice(n))
        self.grid.add(card)
        self.cards[name] = card

    def _fill_menu(self):
        m = self.menu
        m.clear()
        m.addAction("Save as profile…", self.save_dialog)
        m.addSeparator()
        m.addAction("Import profile…", self.import_dialog)
        m.addAction("Export current settings…", self.export_dialog)
        if self.user_profiles:
            m.addSeparator()
            sub = m.addMenu("Delete profile")
            for p in self.user_profiles:
                sub.addAction(p["name"], lambda n=p["name"]: self.delete(n))

    def save_dialog(self):
        name, ok = QInputDialog.getText(self, "Save profile",
                                        "Name for this profile (saves the patches and the Setup answers,\n"
                                        "never the password):", text=self.current() or "")
        if ok and name.strip():
            self.save(name)

    def save(self, name):
        name = name.strip()
        if name in PRESETS:
            QMessageBox.warning(self, "Winsmith", f'"{name}" is a built-in preset. Pick another name.')
            return
        profiles.save_profile(self.win.profile_dir, self.win.current_profile(name))
        self.reload_profiles()

    def import_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import profile", "", "Winsmith profile (*.json)")
        if path:
            self.import_file(path)

    def import_file(self, path):
        try:
            prof = profiles.load_profile(path)
        except ValueError as e:
            QMessageBox.warning(self, "Winsmith", f"Could not import the profile.\n\n{e}")
            return None
        if prof["name"].strip() in PRESETS:
            prof["name"] = f"{prof['name'].strip()} (imported)"
        profiles.save_profile(self.win.profile_dir, prof)
        self.reload_profiles()
        self.win.apply_profile(prof)
        return prof

    def export_dialog(self):
        name = self.current() or "My Winsmith profile"
        path, _ = QFileDialog.getSaveFileName(self, "Export profile", profiles.filename(name),
                                              "Winsmith profile (*.json)")
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            profiles.save_profile(None, self.win.current_profile(name), path)

    def delete(self, name):
        if QMessageBox.question(self, "Winsmith", f'Delete the profile "{name}"?') == QMessageBox.Yes:
            profiles.delete_profile(self.win.profile_dir, name)
            self.reload_profiles()
