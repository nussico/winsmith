import json
import tempfile
import unittest
from pathlib import Path

from winsmith import profiles
from winsmith.patches import PATCHES


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_without_password(self):
        settings = {"user": "pablo", "password": "secret", "language": "de-DE", "iso": "C:\\x.iso"}
        p = profiles.to_profile("Gaming PC", settings, ["tracking", "gamedvr"])
        self.assertNotIn("password", p["setup"])
        self.assertNotIn("iso", p["setup"])
        path = profiles.save_profile(self.dir, p)
        self.assertNotIn("secret", path.read_text(encoding="utf-8"))
        setup, ids = profiles.from_profile(profiles.load_profile(path))
        self.assertEqual(setup["user"], "pablo")
        self.assertEqual(setup["language"], "de-DE")
        self.assertEqual(ids, ["tracking", "gamedvr"])

    def test_old_ids_are_mapped(self):
        setup, ids = profiles.from_profile({"name": "old", "patches": ["telemetry", "adscopilot", "adid"]})
        self.assertEqual(ids, ["tracking", "ads", "ai"])

    def test_unknown_keys_and_patches_dropped(self):
        data = {"name": "x", "version": 1, "patches": ["tracking", "nope"],
                "setup": {"user": "bob", "password": "pw", "evil": 1, "admin": "yes"}}
        setup, ids = profiles.from_profile(data)
        self.assertEqual(ids, ["tracking"])
        self.assertEqual(setup, {"user": "bob"})  # wrong type for admin is ignored too

    def test_bad_files(self):
        bad = self.dir / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            profiles.load_profile(bad)
        bad.write_text(json.dumps({"name": "x", "patches": "telemetry"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            profiles.load_profile(bad)
        bad.write_text(json.dumps([1, 2]), encoding="utf-8")
        with self.assertRaises(ValueError):
            profiles.load_profile(bad)

    def test_list_and_delete(self):
        self.assertEqual(profiles.list_profiles(self.dir / "missing"), [])
        profiles.save_profile(self.dir, profiles.to_profile("B side", {}, list(PATCHES)[:2]))
        profiles.save_profile(self.dir, profiles.to_profile("a/b:c", {}, []))
        names = [p["name"] for p in profiles.list_profiles(self.dir)]
        self.assertEqual(names, ["a/b:c", "B side"])
        profiles.delete_profile(self.dir, "a/b:c")
        self.assertEqual([p["name"] for p in profiles.list_profiles(self.dir)], ["B side"])

    def test_filename_is_safe(self):
        self.assertEqual(profiles.filename("a/b:c*"), "a_b_c_.json")
        self.assertEqual(profiles.filename("  "), "profile.json")

    def test_name_required(self):
        with self.assertRaises(ValueError):
            profiles.to_profile("   ", {}, [])


if __name__ == "__main__":
    unittest.main()
