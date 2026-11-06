"""Regression tests for read-only TMR asset mapping."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_unified_install_sources as audit

BASE = "TMR-Korean-Patcher-v1.0.5/FO4_AE_1.11.191.Kor/"
REQUIRED = {
    "Interface/FontConfig.txt": b"fontconfig",
    "Interface/fonts_en.swf": b"swf",
    "Strings/Fallout4_en.STRINGS": b"base",
    "Strings/Fallout4_en.DLSTRINGS": b"base",
    "Strings/Fallout4_en.ILSTRINGS": b"base",
}


class UnifiedSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "Game" / "Data"
        self.data.mkdir(parents=True)
        for game, filename in audit.GAMES.items():
            (self.data / filename).write_bytes(game.encode())
            folder = self.root / "data" / game
            folder.mkdir(parents=True)
            (folder / "indexed_plan_report.json").write_text(
                json.dumps({"esm_sha256": audit.digest(self.data / filename)}))
            (folder / "current_translation_work_report.json").write_text(
                json.dumps({"translation_work_item_occurrences": 1,
                            "distinct_type_field_english_work_items": 1}))
        self.zip_path = self.root / "test.zip"

    def create_zip(self, extra=None, required=REQUIRED):
        with zipfile.ZipFile(self.zip_path, "w") as z:
            for name, raw in {**required, **(extra or {})}.items():
                z.writestr(BASE + name, raw)

    def analyze(self):
        with patch.object(audit, "ROOT", self.root):
            return audit.inspect(self.zip_path, self.data, check_pin=False)

    def test_ko_only_remapped_but_en_always_preferred(self):
        self.create_zip({
            "Strings/ccExample_ko.STRINGS": "한글 데이터".encode(),
            "Strings/ccBoth_en.STRINGS": b"English",
            "Strings/ccBoth_ko.STRINGS": "한국어 데이터".encode(),
            "Strings/ccTie_en.DLSTRINGS": b"same",
            "Strings/ccTie_ko.DLSTRINGS": b"same",
        })
        before = sorted(str(p) for p in self.data.rglob("*"))
        report = self.analyze()
        outputs = {i["relative_data_path"]: i for i in report["asset_files"]}
        self.assertEqual(outputs["Strings/ccExample_en.STRINGS"]["cc_language_source"], "ko")
        self.assertEqual(outputs["Strings/ccBoth_en.STRINGS"]["cc_language_source"], "en")
        self.assertEqual(outputs["Strings/ccTie_en.DLSTRINGS"]["cc_language_source"], "en")
        self.assertEqual(report["cc_variant_files_with_different_payloads"], 1)
        self.assertEqual(sorted(str(p) for p in self.data.rglob("*")), before)
        self.assertTrue(all(not x["translated_output_ready"] for x in report["converted_esms"].values()))

    def test_local_mo2_folder_and_meta_ignored(self):
        local = self.root / "FO4_AE_1.11.191.Kor"
        for name, raw in REQUIRED.items():
            dest = local / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        (local / "meta.ini").write_text("[General]\\n", encoding="utf-8")
        (local / "Strings" / "ccOnly_ko.STRINGS").write_text("한글", encoding="utf-8")
        with patch.object(audit, "ROOT", self.root):
            result = audit.inspect(local, self.data)
        outputs = {row["relative_data_path"] for row in result["asset_files"]}
        self.assertEqual(result["source_kind"], "installed_mo2_folder")
        self.assertNotIn("meta.ini", outputs)
        self.assertIn("Strings/ccOnly_en.STRINGS", outputs)

    def test_missing_required_font_rejected(self):
        self.create_zip(required={k: v for k, v in REQUIRED.items()
                                  if k != "Interface/fonts_en.swf"})
        with self.assertRaisesRegex(RuntimeError, "Incomplete"):
            self.analyze()

    def test_zip_traversal_rejected(self):
        self.create_zip({"../FO4_AE_1.11.191.Kor/Interface/hack.txt": b"bad"})
        with self.assertRaisesRegex(ValueError, "Unsafe source entry"):
            self.analyze()


if __name__ == "__main__":
    unittest.main()
