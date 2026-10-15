"""Step 3: answer Windows Setup's questions in advance."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from ...unattend import GENERIC_KEYS, account_error, auto_install_error, region_error
from ..page import Page
from ..widgets import Combo, Divider, Field, ResponsiveGrid, Section, ToggleRow, button, set_prop

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

        self.add_left(button("Back", lambda: win.show_page("Patches"), "ghost"))
        self.add_right(button("Next", lambda: win.show_page("Build"), "primary"))
        self.refresh()

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
        for f in (self.f_user, self.f_comp, self.f_lang, self.f_kbd, self.f_install):
            f.set_error(problem[0] if problem and problem[1] is f else None)
        return problem

    def refresh(self):
        for sec in self.sections:
            sec.setVisible(self.win.s["unattended"])
        mode = self.win.s["auto_install"]
        wipe = mode in HINT_ON
        set_prop(self.inst, "warn", wipe)
        self.f_install.hint.setText(HINT_ON.get(mode, HINT_OFF))
        set_prop(self.f_install.hint, "role", "error" if wipe else "small")
        self.win.update_steps()
