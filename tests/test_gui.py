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

    def test_config_round_trip_without_password(self):
        self.w.s["password"] = "secret"
        self.w.s["computer"] = "PC1"
        self.w.pages["Patches"].apply_choice("Everything")
        self.w.save_config()
        data = json.loads(self.win.CONFIG.read_text(encoding="utf-8"))
        self.assertNotIn("password", data)
        w2 = self.new_window()
        try:
            self.assertEqual(w2.s["computer"], "PC1")
            self.assertEqual(w2.s["password"], "")
            self.assertEqual(w2.pages["Patches"].matching(), "Everything")
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
