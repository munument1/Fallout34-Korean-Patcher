"""Small regression tests for strictly supported Fallout34 localization changes."""
import unittest

import recover_complete_sst_exact_text as full
import recover_converted_skill_prefix_dialogue as skill
import recover_fnv_editor_cue_tokens as markers
import recover_fnv_inline_director_cues as director


class ConvertedSstMatching(unittest.TestCase):
    def test_source_editor_cue_inside_a_spoken_line(self):
        english = (
            "{delighted}If it isn't the courier who's done everything "
            "he can to defy the will of mighty {KAI-zar}Caesar!"
        )
        expected = (
            "If it isn't the courier who's done everything "
            "he can to defy the will of mighty Caesar!"
        )
        self.assertIn(
            expected, {v for _, v in director.converted_english_options(english)}
        )

    def test_converter_also_drops_space_after_cue(self):
        english = "stay the fuck out of{outta} other people's business."
        expected = "stay the fuck out ofother people's business."
        self.assertIn(
            expected, {v for _, v in director.converted_english_options(english)}
        )

    def test_no_fuzzy_rewording_or_cueless_transformation(self):
        self.assertEqual(director.converted_english_options("ordinary spoken line"), set())
        self.assertNotIn(
            "I want to leave.",
            {v for _, v in director.converted_english_options("I hope to leave.")},
        )

    def test_korean_editor_notes_removed_like_source(self):
        korean = "{whisper}<고마워요>{No Sound file}"
        self.assertEqual(director.cleaned_korean(korean), "<고마워요>")

    def test_braced_prefix_and_suffix_restoration(self):
        self.assertEqual(
            markers.repair("{Cannibal}People have a unique taste.", "사람은 맛이 독특해."),
            "{Cannibal}사람은 맛이 독특해.",
        )
        self.assertEqual(
            markers.repair("Tell me about Benny.{alive}", "베니에 대해 말해 줘."),
            "베니에 대해 말해 줘.{alive}",
        )
        self.assertIsNone(markers.repair("Unmarked English", "번역된 한국어"))

    def test_skill_label_preserves_dynamic_global_value(self):
        original = "[Speech <Global=F34_F3_SpeechChance_2>%] Make it 400 caps."
        m = skill.REGEX.fullmatch(original)
        self.assertIsNotNone(m)
        self.assertEqual(m["skill"], "Speech")
        self.assertEqual(m["body"], "Make it 400 caps.")
        new = "[" + skill.SKILLS[m["skill"]] + m["suffix"] + "]" + m["separator"] + "400캡으로 해."
        self.assertEqual(full.Counter(full.TOKEN.findall(original)), full.Counter(full.TOKEN.findall(new)))
        self.assertIn("<Global=F34_F3_SpeechChance_2>", new)
        self.assertIn("[화술", new)


if __name__ == "__main__":
    unittest.main()
