"""Ensure only screen-like nonempty text reaches untranslated work reports."""
import unittest

from translation_work_filter import classify


def row(text, record="INFO", field="NAM1", formid="01000001", conditional=None):
    return {
        "formid": formid, "record_type": record, "field": field,
        "english": text, "conditional_proc": conditional,
    }


class TranslationWorkOnly(unittest.TestCase):
    def test_never_translate_whitespace_or_punctuation(self):
        for value in ("", " ", "\r\n\t", "...", "-----", "⚠"):
            self.assertEqual(classify(row(value))[0], "excluded")

    def test_never_translate_base_fo4_master(self):
        self.assertEqual(classify(row("Commonwealth", "WRLD", "FULL", "00001000"))[0], "excluded")

    def test_debug_editor_label_is_not_translation_work(self):
        for value in ("CapitalPostTerminalNote3b", "V03TrentEmail",
                      "TestQAHiuLaiFHair12", "DrunkTestMale",
                      "Auto-Doc Voice (NOT USED IN GAME)"):
            self.assertEqual(classify(row(value, "TERM", "FULL"))[0], "runtime_review")

    def test_current_actual_quest_objective_is_included(self):
        self.assertEqual(classify(row("Return to Moira.", "QUST", "NNAM"))[0], "actionable")
        self.assertEqual(classify(row("Check if barter skill is high?", "QUST", "CNAM"))[0], "runtime_review")

    def test_screen_text_and_item_names_remain(self):
        for rec, field, text in (
            ("INFO", "NAM1", "Hello there, traveler."),
            ("TERM", "UNAM", "From: Vault-Tec\nSubject: Staff training"),
            ("MESG", "DESC", "You cannot open this door."),
            ("MISC", "FULL", "Wasteland Survival Guide"),
            ("ARMO", "FULL", "Power Armor"),
            ("PERK", "DESC", "Your attacks do more damage."),
        ):
            self.assertEqual(classify(row(text, rec, field))[0], "actionable")

    def test_unknown_fields_are_review_not_missing(self):
        self.assertEqual(classify(row("Vertibird", "REFR", "FULL"))[0], "runtime_review")
        self.assertEqual(classify(row("Level up!", "INFO", "NAM1", conditional="P1"))[0], "runtime_review")


if __name__ == "__main__":
    unittest.main()
