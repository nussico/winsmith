import unittest

from winsmith import winget

OUTPUT = (
    "   - \r   \\ \r                                  \r\n"
    "Name                    Id                                Version       Match          Source\n"
    "----------------------------------------------------------------------------------------------\n"
    "Mozilla Firefox         Mozilla.Firefox                   130.0.1       Tag: firefox   winget\n"
    "Firefox Developer Ed.   Mozilla.Firefox.DeveloperEdition  131.0b2                      winget\n"
    "Broken row              not an id                         1.0                          winget\n"
)


class ParseSearchTests(unittest.TestCase):
    def test_parses_rows_and_skips_noise(self):
        found = winget.parse_search(OUTPUT)
        self.assertEqual([f["id"] for f in found], ["Mozilla.Firefox", "Mozilla.Firefox.DeveloperEdition"])
        self.assertEqual(found[0]["name"], "Mozilla Firefox")
        self.assertEqual(found[0]["version"], "130.0.1")

    def test_no_table_is_empty(self):
        self.assertEqual(winget.parse_search("No package found matching input criteria."), [])
        self.assertEqual(winget.parse_search(""), [])


if __name__ == "__main__":
    unittest.main()
