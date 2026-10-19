"""Step 3: answer Windows Setup's questions in advance."""
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QLineEdit, QWidget

from ... import winget
from ...unattend import (GENERIC_KEYS, WIFI_SECURITY, account_error, app_id_ok, auto_install_error, region_error,
                         wifi_error)
from ..page import Page
from ..widgets import Combo, Divider, Field, ResponsiveGrid, Section, ToggleRow, button, hbox, label, set_prop, vbox

ASK = "Ask during setup"
INSTALL_MODES = [("Off: choose the disk during setup", "off"),
                 ("Best SSD: wipe the one clear best disk (10 s to cancel)", "best_ssd"),
                 ("Disk 0: always wipe disk 0", "disk0")]
HINT_OFF = "Off: you pick the disk in setup as usual. The other modes install without asking and wipe that disk."
HINT_ON = {
    "best_ssd": "Prefers NVMe, then SSD, then HDD, never USB or disks under 64 GB, and shows a popup with 10 seconds "
                "to cancel. If two disks tie, normal setup opens. UEFI only. Any PC booted from this ISO can be wiped.",
    "disk0": "Disk 0 is erased without asking. Any PC booted from this ISO can be wiped.",
}
LOCALES = {
    "ar-SA": "Arabic", "cs-CZ": "Czech", "da-DK": "Danish", "de-AT": "German (Austria)", "de-CH": "German (Switzerland)",
    "de-DE": "German (Germany)", "el-GR": "Greek", "en-AU": "English (Australia)", "en-CA": "English (Canada)",
    "en-GB": "English (United Kingdom)", "en-IE": "English (Ireland)", "en-US": "English (United States)",
    "es-ES": "Spanish (Spain)", "es-MX": "Spanish (Mexico)", "fi-FI": "Finnish", "fr-BE": "French (Belgium)",
    "fr-CA": "French (Canada)", "fr-CH": "French (Switzerland)", "fr-FR": "French (France)", "he-IL": "Hebrew",
    "hu-HU": "Hungarian", "it-IT": "Italian", "ja-JP": "Japanese", "ko-KR": "Korean", "nb-NO": "Norwegian",
    "nl-BE": "Dutch (Belgium)", "nl-NL": "Dutch (Netherlands)", "pl-PL": "Polish", "pt-BR": "Portuguese (Brazil)",
    "pt-PT": "Portuguese (Portugal)", "ro-RO": "Romanian", "ru-RU": "Russian", "sk-SK": "Slovak", "sv-SE": "Swedish",
    "th-TH": "Thai", "tr-TR": "Turkish", "uk-UA": "Ukrainian", "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
}
TIMEZONES = ["UTC", "GMT Standard Time", "W. Europe Standard Time", "Central Europe Standard Time",
             "Romance Standard Time", "Central European Standard Time", "GTB Standard Time", "FLE Standard Time",
             "E. Europe Standard Time", "Turkey Standard Time", "Russian Standard Time", "Arabian Standard Time",
             "India Standard Time", "China Standard Time", "Tokyo Standard Time", "Korea Standard Time",
             "AUS Eastern Standard Time", "New Zealand Standard Time", "Eastern Standard Time",
             "Central Standard Time", "Mountain Standard Time", "Pacific Standard Time", "Alaskan Standard Time",
             "Hawaiian Standard Time", "SA Pacific Standard Time", "E. South America Standard Time",
             "Argentina Standard Time", "South Africa Standard Time"]


WIFI_SECURITY_LABELS = [(label_, key) for key, (_, label_) in WIFI_SECURITY.items()]
MAX_RESULTS = 20


class SearchSignals(QObject):
    """winget search runs in a thread; this hands the answer to the UI thread."""
    done = Signal(object, object)  # results, error text


class SetupPage(Page):
    def __init__(self, win):
        super().__init__("Answer setup in advance",
                         "Fill in what Windows Setup would ask, so the install runs on its own.")
        self.win = win
        self.loading = False
        s = win.s

        top = Section()
        self.auto = ToggleRow("Answer setup questions automatically",
                              "Off: Windows Setup asks for account, language and edition as usual. "
                              "Your tweaks still apply.", s["unattended"])
        self.auto.toggled.connect(lambda on: self._set("unattended", on))
        top.body.addWidget(self.auto)
        self.body.addWidget(top)

        acc = Section("Account")
        g = ResponsiveGrid()
        self.f_user = Field("Username", self._line("user"),
                            hint="A local administrator without a password unless you set one. "
                                 "Leave empty to be asked during setup.")
        g.add(self.f_user)
        self.f_pass = Field("Password", self._line("password"), password=True,
                            hint="Optional. Stored base64-encoded on the ISO, not encrypted. Never saved in settings.")
        g.add(self.f_pass)
        self.f_comp = Field("Computer name", self._line("computer"), hint="Leave empty for a random name.")
        g.add(self.f_comp)
        acc.body.addWidget(g)
        acc.body.addSpacing(18)
        acc.body.addWidget(Divider())
        acc.body.addSpacing(16)
        self.admin = ToggleRow("Administrator", "The user can install apps and change system settings.", s["admin"])
        self.admin.toggled.connect(lambda on: self._set("admin", on))
        acc.body.addWidget(self.admin)
        acc.body.addSpacing(14)
        self.skip = ToggleRow("Skip setup screens", "No license, privacy, Microsoft account or network screens.",
                              s["skip_oobe"])
        self.skip.toggled.connect(lambda on: self._set("skip_oobe", on))
        acc.body.addWidget(self.skip)

        reg = Section("Language and region")
        g = ResponsiveGrid()
        self.f_lang = Field("Windows language", self._locale_combo("language"), hint="Must match the ISO's language.")
        g.add(self.f_lang)
        self.f_kbd = Field("Keyboard", self._locale_combo("keyboard"))
        g.add(self.f_kbd)
        self.tz = Combo(TIMEZONES, editable=True)
        self.tz.setCurrentText(s["timezone"])
        self.tz.currentTextChanged.connect(lambda t: self._set("timezone", t))
        g.add(Field("Time zone", self.tz, hint="Windows time zone name (full list: tzutil /l)."), wide=True)
        reg.body.addWidget(g)

        ed = Section("Edition")
        self.edition = Combo([ASK] + list(GENERIC_KEYS))
        self.edition.setCurrentText(s["edition"] or ASK)
        self.edition.currentTextChanged.connect(lambda t: self._set("edition", "" if t == ASK else t))
        ed.body.addWidget(Field("Install edition", self.edition,
                                hint="Uses a generic key that only picks the edition. It does not activate Windows."))

        self.inst = Section("Install")
        self.install = Combo(INSTALL_MODES)
        self.install.setCurrentIndex(max(0, self.install.findData(s["auto_install"])))
        self.install.currentIndexChanged.connect(lambda _: self._set("auto_install", self.install.currentData()))
        self.f_install = Field("Automatic install", self.install, hint=HINT_OFF)
        self.inst.body.addWidget(self.f_install)

        self.sections = [acc, reg, ed, self.inst]
        for sec in self.sections:
            self.body.addWidget(sec)
        self.body.addWidget(self._wifi_section())
        self.body.addWidget(self._apps_section())

        self.add_left(button("Back", lambda: win.show_page("Patches"), "ghost"))
        self.add_right(button("Next", lambda: win.show_page("Build"), "primary"))
        self.refresh()

    # ---------- wifi ----------
    def _wifi_section(self):
        s = self.win.s
        sec = Section("Wi-Fi")
        self.wifi = ToggleRow("Join a Wi-Fi network automatically",
                              "The PC connects to this network on its own after Windows is installed.", s["wifi"])
        self.wifi.toggled.connect(lambda on: self._set("wifi", on))
        sec.body.addWidget(self.wifi)
        self.wifi_box = QWidget()
        box = vbox(self.wifi_box, 0)
        sec.body.addWidget(self.wifi_box)
        g = ResponsiveGrid()
        self.f_ssid = Field("Network name", self._line("wifi_ssid"), hint="Exactly as it appears in the Wi-Fi list.")
        g.add(self.f_ssid)
        self.f_wpass = Field("Password", self._line("wifi_password"), password=True,
                             hint="Stored in plain text on the ISO. Never saved in settings or profiles.")
        g.add(self.f_wpass)
        self.wsec = Combo(WIFI_SECURITY_LABELS)
        self.wsec.setCurrentIndex(max(0, self.wsec.findData(s["wifi_security"])))
        self.wsec.currentIndexChanged.connect(lambda _: self._set("wifi_security", self.wsec.currentData()))
        g.add(Field("Security", self.wsec))
        box.addSpacing(14)
        box.addWidget(g)
        box.addSpacing(14)
        self.whidden = ToggleRow("Hidden network", "The network does not broadcast its name.", s["wifi_hidden"])
        self.whidden.toggled.connect(lambda on: self._set("wifi_hidden", on))
        box.addWidget(self.whidden)
        return sec

    # ---------- apps ----------
    def _apps_section(self):
        sec = Section("Apps")
        self.signals = SearchSignals()
        self.signals.done.connect(self._show_results)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search winget, or type an ID like Mozilla.Firefox")
        self.search_edit.returnPressed.connect(self._search)
        self.f_apps = Field("Install after Windows is set up", self.search_edit,
                            hint="Installed with winget at the first sign-in. The PC needs internet then.")
        self.search_btn = button("Search", self._search)
        self.add_btn = button("Add ID", self._add_typed, "ghost")
        self.f_apps.row.addWidget(self.search_btn)
        self.f_apps.row.addWidget(self.add_btn)
        sec.body.addWidget(self.f_apps)
        self.has_winget = winget.available()
        self.search_btn.setVisible(self.has_winget)
        if not self.has_winget:
            self.f_apps.hint.setText("winget was not found on this PC, so type the package ID "
                                     "(like Mozilla.Firefox) and press Add ID.")
        self.results = QWidget()
        self.results_box = vbox(self.results, 4)
        sec.body.addWidget(self.results)
        sec.body.addSpacing(10)
        self.chosen = QWidget()
        self.chosen_box = vbox(self.chosen, 4)
        sec.body.addWidget(self.chosen)
        self._fill_chosen()
        return sec

    def _search(self):
        query = self.search_edit.text().strip()
        if not query or not self.has_winget:
            return
        self.f_apps.set_error(None)
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Searching…")

        def work():
            try:
                self.signals.done.emit(winget.search(query), None)
            except Exception as e:
                self.signals.done.emit([], str(e) or type(e).__name__)

        threading.Thread(target=work, daemon=True).start()

    def _show_results(self, found, err):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        self._clear(self.results_box)
        if err or not found:
            self.f_apps.set_error(err or "Nothing found.")
        for app in found[:MAX_RESULTS]:
            self.results_box.addWidget(self._row(f"{app['name']}  ·  {app['id']}  {app['version']}", app["id"]))

    def _add_typed(self):
        text = self.search_edit.text().strip()
        if not app_id_ok(text):
            self.f_apps.set_error("That is not a winget package ID. Search for it, or type one like Mozilla.Firefox.")
            return
        self.f_apps.set_error(None)
        self._add(text)
        self.search_edit.clear()

    def _pick(self, app_id):
        """Add from the search results, then reset the search for the next one."""
        self._add(app_id)
        self.search_edit.clear()
        self._clear(self.results_box)
        self.f_apps.set_error(None)

    def _add(self, app_id):
        if app_id not in self.win.s["apps"]:
            self._set("apps", self.win.s["apps"] + [app_id])
        self._fill_chosen()

    def _remove(self, app_id):
        self._set("apps", [a for a in self.win.s["apps"] if a != app_id])
        self._fill_chosen()

    def _row(self, text, app_id, chosen=False):
        row = QWidget()
        lay = hbox(row, 8)
        lay.addWidget(label(text, wrap=True), 1)
        if chosen:
            lay.addWidget(button("Remove", lambda: self._remove(app_id), "ghost"))
        else:
            added = app_id in self.win.s["apps"]
            b = button("Added" if added else "Add", lambda: self._pick(app_id), "ghost")
            b.setEnabled(not added)
            lay.addWidget(b)
        return row

    @staticmethod
    def _clear(box):
        while box.count():
            w = box.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _fill_chosen(self):
        self._clear(self.chosen_box)
        for app_id in self.win.s["apps"]:
            self.chosen_box.addWidget(self._row(app_id, app_id, chosen=True))

    def _set(self, key, value):
        self.win.s[key] = value
        if not self.loading:
            self.refresh()

    def _line(self, key):
        e = QLineEdit(self.win.s[key])
        e.textChanged.connect(lambda t: self._set(key, t))
        return e

    def _locale_combo(self, key):
        """'German (Germany)  ·  de-DE' entries sorted by name, holding just the code, plus an unknown code from an old config."""
        codes = sorted(LOCALES, key=LOCALES.get)
        if self.win.s[key] not in LOCALES:
            codes.append(self.win.s[key])
        c = Combo([(f"{LOCALES[code]}  ·  {code}" if code in LOCALES else code, code) for code in codes])
        c.setCurrentIndex(c.findData(self.win.s[key]))
        c.currentIndexChanged.connect(lambda _: self._set(key, c.currentData()))
        return c

    def load(self):
        """Show the values in win.s (after a profile was applied)."""
        s = self.win.s
        self.loading = True
        try:
            self.auto.setChecked(s["unattended"])
            self.admin.setChecked(s["admin"])
            self.skip.setChecked(s["skip_oobe"])
            for f, key in ((self.f_user, "user"), (self.f_comp, "computer")):
                f.input.setText(s[key])
            for f, key in ((self.f_lang, "language"), (self.f_kbd, "keyboard")):
                c = f.input
                if c.findData(s[key]) < 0:
                    c.addItem(s[key], s[key])
                c.setCurrentIndex(c.findData(s[key]))
            self.tz.setCurrentText(s["timezone"])
            self.edition.setCurrentText(s["edition"] or ASK)
            self.install.setCurrentIndex(max(0, self.install.findData(s["auto_install"])))
            self.f_pass.input.setText(s["password"])
            self.wifi.setChecked(s["wifi"])
            self.f_ssid.input.setText(s["wifi_ssid"])
            self.f_wpass.input.setText(s["wifi_password"])
            self.wsec.setCurrentIndex(max(0, self.wsec.findData(s["wifi_security"])))
            self.whidden.setChecked(s["wifi_hidden"])
            self._fill_chosen()
        finally:
            self.loading = False
        self.refresh()

    def validate(self):
        """Returns (problem, field to point at) or None, and marks the field."""
        v = self.win.s
        problem = None
        if v["unattended"]:  # off: nothing from this page goes into the answer file
            err = account_error(v["user"], v["computer"], v["admin"], v["skip_oobe"])
            if err:
                problem = (err, self.f_comp if err.startswith("Computer name") else self.f_user)
            else:
                err = region_error(v["language"], v["keyboard"])
                if err:
                    problem = (err, self.f_lang if err.startswith("Windows language") else self.f_kbd)
                elif auto_install_error(v):
                    problem = (auto_install_error(v), self.f_install)
        err = None
        if v["wifi"]:
            err = "Enter the Wi-Fi network name." if not v["wifi_ssid"].strip() else                 wifi_error(v["wifi_ssid"], v["wifi_password"], v["wifi_security"])
        if err and not problem:
            problem = (err, self.f_wpass if "password" in err else self.f_ssid)
        for f in (self.f_user, self.f_comp, self.f_lang, self.f_kbd, self.f_install, self.f_ssid, self.f_wpass):
            f.set_error(problem[0] if problem and problem[1] is f else None)
        return problem

    def refresh(self):
        self.wifi_box.setVisible(self.win.s["wifi"])
        for sec in self.sections:
            sec.setVisible(self.win.s["unattended"])
        mode = self.win.s["auto_install"]
        wipe = mode in HINT_ON
        set_prop(self.inst, "warn", wipe)
        self.f_install.hint.setText(HINT_ON.get(mode, HINT_OFF))
        set_prop(self.f_install.hint, "role", "error" if wipe else "small")
        self.win.update_steps()
