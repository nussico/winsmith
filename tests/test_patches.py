import unittest

from winsmith.patches import ALIASES, PATCHES, PRESETS, resolve
from winsmith.unattend import _reg_cmd


class CatalogTests(unittest.TestCase):
    def test_resolve_aliases(self):
        self.assertEqual(resolve(["telemetry", "adscopilot", "activity", "nope", "gamedvr"]),
                         ["tracking", "ads", "ai", "gamedvr"])
        self.assertEqual(resolve(["nosearchbox", "notaskview", "tidytaskbar"]), ["tidytaskbar"])
        self.assertEqual(resolve([]), [])
        self.assertEqual(resolve([1, None, "fileext"]), ["fileext"])

    def test_aliases_point_to_real_patches(self):
        for old, new in ALIASES.items():
            self.assertNotIn(old, PATCHES)
            self.assertTrue(set(new) <= set(PATCHES), old)

    def test_every_patch_is_complete(self):
        for pid, p in PATCHES.items():
            self.assertTrue(p["group"] and p["label"] and p["desc"], pid)
            self.assertTrue(p["reg"] or p["apps"] or p["script"], pid)
            for e in p["reg"]:
                self.assertTrue(e.split("\\")[0] in ("SYSTEM", "SOFTWARE", "DEFAULT"), e)
                _reg_cmd(e)  # parses

    def test_catalog_shape(self):
        self.assertEqual(len(PATCHES), 28)
        self.assertEqual(len({p["group"] for p in PATCHES.values()}), 8)
        self.assertEqual(PRESETS["Basic"], ["hwchecks", "localaccount", "skipprivacy", "nobitlocker"])
        self.assertEqual(PRESETS["Everything"], list(PATCHES))
        for ids in PRESETS.values():
            self.assertTrue(set(ids) <= set(PATCHES))


if __name__ == "__main__":
    unittest.main()
