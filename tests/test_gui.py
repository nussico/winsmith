import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # GUI tests need PySide6
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from winsmith.ui import theme, window
        cls.win = window
        cls.app = QApplication.instance() or QApplication([])
        theme.apply(cls.app)

    def setUp(self):
        # Never read or write the user's real settings or profiles.
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = mock.patch.multiple(self.win, CONFIG=Path(self.tmp.name) / "config.json",
                                           OLD_CONFIG=Path(self.tmp.name) / "old.json")
        self.patcher.start()
        self.w = self.new_window()

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.patcher.stop()
        self.tmp.cleanup()

    def new_window(self):
        w = self.win.MainWindow()
        w.show()
        self.app.processEvents()
        return w

    def test_fresh_defaults(self):
        from winsmith.patches import PRESETS
        self.assertEqual(self.w.s["user"], "User")
        self.assertFalse(self.w.s["unattended"])
        self.assertTrue(all(sec.isHidden() for sec in self.w.pages["Setup"].sections))
        self.assertEqual(self.w.selected(), [p for p in PRESETS["Basic"]])
        self.assertEqual(self.w.pages["Patches"].matching(), "Basic")

    def test_step_switching(self):
        for name in self.win.PAGES:
            self.w.show_page(name)
            self.assertIs(self.w.stack.currentWidget(), self.w.pages[name])
        self.w._step(1)
        self.assertEqual(self.w.current, "Source")

    def test_presets_and_custom(self):
        pat = self.w.pages["Patches"]
        pat.apply_choice("Everything")
        self.assertEqual(pat.matching(), "Everything")
        pid = next(iter(pat.rows))
        pat.rows[pid].setChecked(False)
        self.assertIsNone(pat.matching())
        self.assertIsNone(pat.current())
        self.assertFalse(pat.custom.isHidden())
        self.assertFalse(pat.list.isHidden())  # a custom mix opens the full list
        pat.apply_choice("Basic")
        self.assertEqual(pat.current(), "Basic")
        self.assertTrue(pat.custom.isHidden())

    def test_customize_toggles_list(self):
        pat = self.w.pages["Patches"]
        self.assertTrue(pat.list.isHidden())
        pat.customize.click()
        self.assertFalse(pat.list.isHidden())
        self.assertEqual(pat.customize.text(), "Hide tweaks")
        pat.customize.click()
        self.assertTrue(pat.list.isHidden())

    def test_card_click_applies_preset(self):
        pat = self.w.pages["Patches"]
        pat.cards["Everything"].clicked.emit()
        self.assertEqual(pat.matching(), "Everything")
        self.assertTrue(pat.cards["Everything"].property("selected"))
        self.assertFalse(pat.cards["Basic"].property("selected"))

    def test_stepper_dots_stay_put(self):
        st = self.w.stepper
        for width in (1000, 480):
            self.w.resize(width, 700)
            self.app.processEvents()
            spots = [st.dot_rect(n) for n in st.names]
            for name in self.win.PAGES:
                self.w.show_page(name)
                self.app.processEvents()
                self.assertEqual([st.dot_rect(n) for n in st.names], spots)
            self.w.pages["Patches"].apply_choice("Everything")
            st.set_status("Source", "A much longer status text than usual", "error")
            self.app.processEvents()
            self.assertEqual([st.dot_rect(n) for n in st.names], spots)

    def test_setup_validation_and_switch(self):
        setup = self.w.pages["Setup"]
        setup.auto.setChecked(True)
        setup.f_comp.input.setText("bad name!")
        problem = setup.validate()
        self.assertIsNotNone(problem)
        self.assertIs(problem[1], setup.f_comp)
        setup.auto.setChecked(False)
        self.assertIsNone(setup.validate())
        self.assertTrue(all(sec.isHidden() for sec in setup.sections))

    def test_auto_install_section(self):
        setup = self.w.pages["Setup"]
        self.assertEqual(self.w.s["auto_install"], "off")
        self.assertTrue(setup.inst.isHidden())  # setup answers are off by default
        setup.auto.setChecked(True)
        self.assertFalse(setup.inst.isHidden())
        setup.edition.setCurrentIndex(0)  # ask during setup
        setup.install.setCurrentIndex(setup.install.findData("best_ssd"))
        problem = setup.validate()
        self.assertIsNotNone(problem)
        self.assertIs(problem[1], setup.f_install)
        self.assertTrue(setup.inst.property("warn"))
        setup.edition.setCurrentText("Pro")
        self.assertIsNone(setup.validate())
        self.assertEqual(self.w.stepper.status["Setup"], ("Wipes best SSD", "error"))
        setup.install.setCurrentIndex(setup.install.findData("off"))
        self.assertFalse(setup.inst.property("warn"))

    def test_locale_combo_keeps_code(self):
        setup = self.w.pages["Setup"]
        c = setup.f_lang.input
        c.setCurrentIndex(c.findData("de-DE"))
        self.assertEqual(self.w.s["language"], "de-DE")

    def test_check_points_to_source(self):
        msg, page, field = self.w.check()
        self.assertEqual(page, "Source")
        self.assertIs(field, self.w.pages["Source"].field)

    def test_bad_remembered_iso_or_config_still_starts(self):
        for body in ('{"iso": "D:\\\\"}', '{"iso": "."}', '[]', 'null', '{"last_update_check": "x"}',
                     '{"last_update_check": NaN}', '{"last_update_check": 1' + "0" * 400 + "}"):
            self.win.CONFIG.write_text(body, encoding="utf-8")
            w2 = self.new_window()
            try:
                self.assertEqual(w2.last_update_check, 0.0)
            finally:
                w2.close()
                w2.deleteLater()

    def test_old_config_keys_are_ignored(self):
        self.win.CONFIG.write_text(json.dumps({"computer": "OLD", "password": "x", "patches": ["tracking"]}), encoding="utf-8")
        w2 = self.new_window()
        try:
            self.assertEqual((w2.s["computer"], w2.s["password"]), ("", ""))
            self.assertEqual(w2.pages["Patches"].matching(), "Basic")
        finally:
            w2.close()
            w2.deleteLater()

    def test_only_the_base_iso_is_remembered(self):
        from winsmith import iso as iso_mod
        self.w.s["password"] = "secret"
        self.w.s["wifi_password"] = "secret123"
        self.w.s["computer"] = "PC1"
        self.w.s["iso"] = "C:/isos/Win11.iso"
        self.w.s["output"] = "C:/out/mine.iso"
        self.w.pages["Patches"].apply_choice("Everything")
        self.w.save_config()
        data = json.loads(self.win.CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"iso", "last_update_check"})
        w2 = self.new_window()
        try:
            self.assertEqual(w2.s["iso"], "C:/isos/Win11.iso")
            self.assertEqual(w2.s["computer"], "")
            self.assertEqual(w2.s["password"], "")
            self.assertEqual(w2.pages["Patches"].matching(), "Basic")
            self.assertTrue(iso_mod.is_auto_name(w2.s["output"]))
        finally:
            w2.close()
            w2.deleteLater()

    def test_profile_save_and_apply(self):
        pat, setup = self.w.pages["Patches"], self.w.pages["Setup"]
        pat.apply_choice("Recommended")
        setup.f_user.input.setText("Alice")
        pat.save("Mine")
        self.assertIn("Mine", [p["name"] for p in pat.user_profiles])
        self.assertEqual(pat.matching(), "Mine")
        pat.apply_choice("Basic")
        setup.f_user.input.setText("Bob")
        pat.apply_choice("Mine")
        self.assertEqual(self.w.s["user"], "Alice")
        self.assertEqual(setup.f_user.input.text(), "Alice")
        self.assertEqual(pat.matching(), "Mine")

    def test_import_profile(self):
        from winsmith import profiles
        path = Path(self.tmp.name) / "x.json"
        path.write_text(json.dumps(profiles.to_profile("Basic", {"user": "Eve"}, [])), encoding="utf-8")
        prof = self.w.pages["Patches"].import_file(str(path))
        self.assertEqual(prof["name"], "Basic (imported)")
        self.assertEqual(self.w.s["user"], "Eve")
        self.assertEqual(self.w.selected(), [])

    def test_install_oscdimg_button(self):
        from winsmith import iso
        from winsmith.ui.widgets import QPushButton
        page = self.w.pages["Build"]
        missing = [("oscdimg", "winget install Microsoft.WindowsADK")]
        with mock.patch.object(iso, "missing_tools", side_effect=lambda: missing), \
                mock.patch.object(iso, "can_install_oscdimg", return_value=True), \
                mock.patch.object(iso, "install_oscdimg", side_effect=lambda log: missing.clear()) as inst, \
                mock.patch("threading.Thread", lambda target, daemon=None: mock.Mock(start=target)):  # run inline
            page.refresh()
            self.assertFalse(page.build_btn.isEnabled())
            btn = next(b for b in page.tools.findChildren(QPushButton) if b.text() == "Install it for me")
            btn.click()
            self.app.processEvents()
            self.assertFalse(page.installing)
            inst.assert_called_once()
            self.assertTrue(page.tools.isHidden())
            self.assertTrue(page.build_btn.isEnabled())
            self.assertEqual(page.status.text(), "oscdimg installed")

    def test_install_failure_keeps_build_disabled(self):
        from winsmith import iso
        page = self.w.pages["Build"]
        missing = [("oscdimg", "winget install Microsoft.WindowsADK")]
        with mock.patch.object(iso, "missing_tools", side_effect=lambda: missing), \
                mock.patch.object(iso, "can_install_oscdimg", return_value=True):
            page.installing = True
            page._installed("oscdimg is still missing.\nThe installer reported: declined")
            self.assertFalse(page.installing)
            self.assertFalse(page.build_btn.isEnabled())
            self.assertFalse(page.tools.isHidden())
            page._installed(None)  # reported success but the tool is still missing
            self.assertFalse(page.build_btn.isEnabled())
            page.building = True
            page._finish("boom")
            self.assertFalse(page.build_btn.isEnabled())

    REL = {"version": "9.9.9", "page": "https://github.com/nussico/winsmith/releases/tag/v9.9.9",
           "asset_url": "https://github.com/nussico/winsmith/releases/download/v9.9.9/Winsmith.exe", "size": 3}

    def test_banner_hidden_until_update_found(self):
        self.assertTrue(self.w.banner.isHidden())
        with mock.patch.object(self.win.updater, "is_frozen", return_value=True):
            self.w._show_update(self.REL)
        self.assertFalse(self.w.banner.isHidden())
        self.assertIn("9.9.9", self.w.banner.text.text())
        self.assertFalse(self.w.banner.update_btn.isHidden())
        self.assertTrue(self.w.banner.copy_btn.isHidden())
        self.w.banner.later_btn.click()
        self.assertTrue(self.w.banner.isHidden())

    def test_banner_for_python_install_shows_command_only(self):
        with mock.patch.object(self.win.updater, "is_frozen", return_value=False):
            self.w._show_update(self.REL)
        self.assertTrue(self.w.banner.update_btn.isHidden())
        self.assertFalse(self.w.banner.copy_btn.isHidden())

    def test_check_skipped_when_not_due(self):
        import time
        self.w.last_update_check = time.time()
        with mock.patch.object(self.win.updater, "check") as chk:
            self.w.check_for_updates()
        chk.assert_not_called()

    def test_check_finds_update_and_stores_time(self):
        self.w.last_update_check = 0
        with mock.patch.object(self.win.updater, "latest_release", return_value=self.REL),                 mock.patch.object(self.win.updater, "is_frozen", return_value=True),                 mock.patch("threading.Thread", lambda target, daemon=None: mock.Mock(start=target)):
            self.w.check_for_updates()
        self.app.processEvents()
        self.assertFalse(self.w.banner.isHidden())
        self.assertGreater(self.w.last_update_check, 0)

    def test_update_blocked_while_installing(self):
        build = self.w.pages["Build"]
        build.installing = True
        try:
            with mock.patch.object(self.win.updater, "download") as dl:
                self.w.start_update(self.REL)
        finally:
            build.installing = False
        dl.assert_not_called()
        self.assertIn("install", self.w.banner.text.text().lower())

    def test_update_downloads_swaps_and_restarts(self):
        up = self.win.updater
        with mock.patch.object(up, "exe_path", return_value=Path(self.tmp.name) / "Winsmith.exe"),                 mock.patch.object(up, "download") as dl, mock.patch.object(up, "apply") as ap,                 mock.patch.object(up, "relaunch") as rl,                 mock.patch.object(self.win.QApplication, "quit") as quit_,                 mock.patch("threading.Thread", lambda target, daemon=None: mock.Mock(start=target)):
            self.w.start_update(self.REL)
            self.app.processEvents()
        dl.assert_called_once()
        ap.assert_called_once()
        rl.assert_called_once()
        quit_.assert_called()

    def test_update_failure_keeps_app_and_shows_error(self):
        up = self.win.updater
        with mock.patch.object(up, "exe_path", return_value=Path(self.tmp.name) / "Winsmith.exe"),                 mock.patch.object(up, "download", side_effect=OSError("disk full")),                 mock.patch.object(up, "relaunch") as rl,                 mock.patch.object(up, "is_frozen", return_value=True),                 mock.patch("threading.Thread", lambda target, daemon=None: mock.Mock(start=target)):
            self.w._show_update(self.REL)
            self.w.banner.update_btn.click()
            self.app.processEvents()
        rl.assert_not_called()
        self.assertIn("disk full", self.w.banner.text.text())
        self.assertFalse(self.w.banner.update_btn.isHidden())

    def test_apps_add_remove_and_profile_roundtrip(self):
        page = self.w.pages["Setup"]
        page.search_edit.setText("bad id")
        page._add_typed()
        self.assertEqual(self.w.s["apps"], [])
        self.assertFalse(page.f_apps.error.isHidden())
        page.search_edit.setText("Mozilla.Firefox")
        page._add_typed()
        page._add("Mozilla.Firefox")  # no duplicates
        page.search_edit.setText("fire")
        page._show_results([{"name": "7-Zip", "id": "7zip.7zip", "version": "1"}], None)
        self.assertEqual(page.results_box.count(), 1)
        page._pick("7zip.7zip")
        self.assertEqual(page.search_edit.text(), "")
        self.assertEqual(page.results_box.count(), 0)
        page._remove("7zip.7zip")
        self.assertEqual(self.w.s["apps"], ["Mozilla.Firefox"])
        prof = self.w.current_profile("p")
        self.assertEqual(prof["setup"]["apps"], ["Mozilla.Firefox"])
        page._remove("Mozilla.Firefox")
        self.assertEqual(self.w.s["apps"], [])
        self.w.apply_profile(prof)
        self.assertEqual(self.w.s["apps"], ["Mozilla.Firefox"])
        self.assertEqual(page.chosen_box.count(), 1)

    def test_save_profile_asks_before_keeping_passwords(self):
        from PySide6.QtWidgets import QMessageBox
        from winsmith import profiles
        page = self.w.pages["Patches"]
        name = "pwtest"
        path = self.w.profile_dir / profiles.filename(name)
        with mock.patch.object(QMessageBox, "question") as q:
            page.save(name)  # no passwords filled in: no question
            q.assert_not_called()
            self.assertNotIn("wifi_password", json.loads(path.read_text())["setup"])
            self.w.s["wifi_password"] = "longenough1"
            self.w.s["password"] = "pw"
            q.return_value = QMessageBox.No
            page.save(name)
            self.assertEqual(q.call_count, 1)
            self.assertNotIn("wifi_password", json.loads(path.read_text())["setup"])
            q.return_value = QMessageBox.Yes
            page.save(name)
            setup = json.loads(path.read_text())["setup"]
            self.assertEqual((setup["wifi_password"], setup["password"]), ("longenough1", "pw"))
        self.w.s["wifi_password"] = self.w.s["password"] = ""
        self.w.apply_profile(json.loads(path.read_text()))
        self.assertEqual(self.w.s["wifi_password"], "longenough1")
        self.assertEqual(self.w.pages["Setup"].f_pass.input.text(), "pw")

    def test_wifi_validation_and_profile_excludes_password(self):
        page = self.w.pages["Setup"]
        page.wifi.setChecked(True)
        self.assertIsNotNone(page.validate())  # no network name yet
        page.f_ssid.input.setText("Home")
        page.f_wpass.input.setText("short")
        self.assertIsNotNone(page.validate())
        page.f_wpass.input.setText("longenough1")
        self.assertIsNone(page.validate())
        prof = self.w.current_profile("p")
        self.assertEqual(prof["setup"]["wifi_ssid"], "Home")
        self.assertNotIn("wifi_password", prof["setup"])

    def test_import_old_profile_maps_ids(self):
        path = Path(self.tmp.name) / "old.json"
        path.write_text(json.dumps({"name": "Old", "patches": ["telemetry", "adscopilot", "notaskview"]}),
                        encoding="utf-8")
        self.w.pages["Patches"].import_file(str(path))
        self.assertEqual(set(self.w.selected()), {"ai", "tracking", "ads", "tidytaskbar"})

    def test_narrow_window_has_no_horizontal_scroll(self):
        self.w.resize(480, 600)
        for name in self.win.PAGES:
            self.w.show_page(name)
            self.app.processEvents()
            page = self.w.pages[name]
            self.assertLessEqual(page.minimumSizeHint().width(), 480)
            self.assertFalse(page.scroll.horizontalScrollBar().isVisible(), name)
        self.assertFalse(self.w.brand.isVisible())


if __name__ == "__main__":
    unittest.main()
