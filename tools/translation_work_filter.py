"""Strict, presentation-focused selection for Fallout34 untranslated WORK items.

An xTranslator residual field is not automatically a string that the player
sees. The owner of the field may be Fallout4.esm, the text may be blank, a
debug/editor identifier or generated processing data. Such records belong in
the forensic audit, NOT in the end-user "remaining translation work" report.

Without real runtime playtesting, we do not have a proof that every remaining
UI-shaped field is reachable. Thus these are *human-visible translation work
candidates*, never claimed to be confirmed in-game missing strings.
"""
from __future__ import annotations

import re

# Only record fields with reasonably established on-screen roles. Quest NNAM
# was mistakenly excluded by the earlier broad xTranslator field taxonomy.
# Conversely many QUST/CNAM are debug/condition labels, NOT objectives.
SCREEN_FIELDS = {
    ("INFO", "NAM1"), ("INFO", "RNAM"),
    ("TERM", "ITXT"), ("TERM", "BTXT"), ("TERM", "UNAM"),
    ("TERM", "RNAM"), ("TERM", "FULL"),
    ("MESG", "ITXT"), ("MESG", "DESC"), ("MESG", "FULL"),
    ("QUST", "NNAM"),
    ("BOOK", "DESC"), ("BOOK", "FULL"),
    ("LSCR", "DESC"),
    ("NPC_", "FULL"), ("WEAP", "FULL"), ("ARMO", "FULL"),
    ("AMMO", "FULL"), ("MISC", "FULL"), ("ALCH", "FULL"),
    ("KEYM", "FULL"), ("CELL", "FULL"), ("WRLD", "FULL"),
    ("PERK", "FULL"), ("PERK", "DESC"),
    ("CONT", "FULL"), ("ACTI", "FULL"), ("FURN", "FULL"),
    ("DOOR", "FULL"), ("TACT", "FULL"),
}

# These are at best uncertain. Do not assume an original editor label is a
# title that a player sees. E.g. QUST/CNAM has 'Check if barter skill...'
# while actual objective texts are QUST/NNAM in this converted data.
RUNTIME_REVIEW_FIELDS = {
    ("QUST", "CNAM"), ("FACT", "FULL"), ("NOTE", "FULL"),
    ("NOTE", "DESC"), ("AVIF", "FULL"), ("MGEF", "FULL"),
    ("SPEL", "FULL"), ("SPEL", "DESC"), ("ENCH", "FULL"),
    ("AMMO", "ONAM"), ("ALCH", "DESC"),
}

UNUSED = re.compile(
    r"(?i)(?:NOT USED IN GAME|NOT[ -]?USED|DO NOT USE|DONT USE|"
    r"LEVEL DESIGN TOOLBOX|DEBUG CELL|TESTING CELL|"
    r"^QA[\w-]+$|^TestQA[\w-]*$)"
)
EDITOR_ID = re.compile(
    r"^(?:"
    r"[A-Za-z]{1,5}\d{2,}[A-Za-z0-9_]*|"       # MS01..., NVDLC03...
    r"[A-Za-z0-9]*_[A-Za-z0-9_]+|"                # EditorUnique_2
    r"(?:[A-Za-z]+[0-9]+){2,}[A-Za-z0-9]*|"
    r"[a-z]?[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+){2,}\d*"
    r")$"
)
TEST_ID = re.compile(r"(?i)^(?:debug|test|qa)[A-Z0-9_].{2,}$")


def classify(row):
    """Return (class, reason), using a conservative whitelist.

    - actionable: readable text in a real on-screen semantic field;
    - runtime_review: uncertain whether that field/string is displayed;
    - excluded: empty/symbol/foreign master/editor-only/conditional.
    """
    formid = int(row["formid"], 16)
    text = row["english"]
    if (formid >> 24) == 0:
        return "excluded", "fallout4_master_not_fo3_fnv"
    if not text.strip():
        return "excluded", "empty_or_whitespace"
    if not any(ch.isalnum() for ch in text):
        return "excluded", "symbols_only"
    if row["conditional_proc"] is not None:
        return "runtime_review", "conditional_record"

    pair = row["record_type"], row["field"]
    if pair not in SCREEN_FIELDS:
        return "runtime_review", "field_visibility_not_established"

    # Do not reclassify entire multiline text content as an editor ID because
    # it happens to contain internal snippets (e.g. RobCo terminal logs).
    if "\r" not in text and "\n" not in text:
        if UNUSED.search(text):
            return "runtime_review", "explicitly_test_or_unused"
        if TEST_ID.match(text) or EDITOR_ID.fullmatch(text):
            return "runtime_review", "looks_like_editor_identifier"
        if text.isdigit():
            return "runtime_review", "numeric_only"
    return "actionable", "player_facing_field_nonempty_text"
