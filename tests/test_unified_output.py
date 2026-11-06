"""Regression tests for the bundled Fallout 4 localization installer stage."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_unified_install_output as installer


class BundledKoreanOutput(unittest.TestCase):
    def test_checked_in_resource_inventory_integrity(self):
        inventory = installer.check_bundled()
        self.assertEqual(len(inventory["files"]), 565)
        self.assertTrue((installer.BUNDLED / "Interface" / "fonts_en.swf").is_file())
        self.assertTrue((installer.BUNDLED / "Strings" / "Fallout4_en.STRINGS").is_file())
        self.assertNotIn("meta.ini", inventory["files"])

    def test_inspect_does_not_create_output(self):
        info = installer.preflight(installer.DEFAULT_GAME_DATA)
        self.assertEqual(info["bundled_files"], 565)
        self.assertFalse(info["ready_to_build"])
        self.assertGreater(info["remaining"]["fo3"]["work_field_occurrences"], 0)
        self.assertGreater(info["remaining"]["fnv"]["work_field_occurrences"], 0)

    def test_incomplete_translations_do_not_generate_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            fake_fo3, fake_fnv = root / "Fallout34.esm", root / "FalloutNV34.esm"
            fake_fo3.write_bytes(b"not an ESM")
            fake_fnv.write_bytes(b"not an ESM")
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                installer.create(installer.DEFAULT_GAME_DATA, output, {
                    "fo3": fake_fo3,
                    "fnv": fake_fnv,
                })
            self.assertFalse(output.exists())

    def test_never_write_into_game_data(self):
        with self.assertRaisesRegex(ValueError, "overlaps protected"):
            installer.create(
                installer.DEFAULT_GAME_DATA,
                installer.DEFAULT_GAME_DATA / "mods" / "Fallout34-Translated",
                {},
            )


if __name__ == "__main__":
    unittest.main()
