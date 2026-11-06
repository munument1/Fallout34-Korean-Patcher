"""Recover player dialogue translated in the original ESM/SST but prefixed by Fallout34 skill labels.

Converted FO4 INFO/RNAM/NAM1 may read
  [Speech <Global=F34_F3_SpeechChance_2>%] Make it 400 caps...
while the FO3/TTW or FNV original DIAL/FULL (and its Korean SST) reads
  Make it 400 caps...

This finds only known Fallout skill labels and exact original English bodies.
It checks that the body exists in an original game's ESM dialogue source
field, and that its complete original-game SST family provides ONE Korean.
It localizes the label while preserving numeric/dynamic content exactly.
Speaker/quest identity is still subject to contextual QA. Writes no ESM.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import gzip
import json
from pathlib import Path
import re

import recover_complete_sst_exact_text as common

SKILLS = {
    "Energy Weapons": "에너지 무기",
    "Melee Weapons": "근접 무기",
    "Explosives": "폭발물",
    "Intelligence": "지능",
    "Perception": "인지력",
    "Endurance": "지구력",
    "Strength": "힘",
    "Charisma": "매력",
    "Medicine": "의학",
    "Lockpick": "자물쇠 따기",
    "Science": "과학",
    "Survival": "생존",
    "Speech": "화술",
    "Repair": "수리",
    "Barter": "흥정",
    "Sneak": "은신",
    "Agility": "민첩성",
    "Guns": "총기",
    "Luck": "운",
    "Unarmed": "비무장",
}
REGEX = re.compile(
    r"^\[(?P<skill>" + "|".join(re.escape(x) for x in SKILLS) +
    r")(?P<suffix>(?:\s+[^\]]*)?)\](?P<separator>[ \t]+)(?P<body>[^\r\n]+)$"
)
NATIVE_FIELDS = {("INFO", "RNAM"), ("INFO", "NAM1"), ("DIAL", "FULL")}


def run(game):
    native = common.module("native_skill", "recover_fnv_xtranslator_origin_verified.py")
    fo3 = common.module("fo3_skill", "recover_fo3_xtranslator_provenance.py")
    parser = common.module("sst_skill", "read_xtranslator_sst.py")
    d = common.ROOT / "data" / game
    installed = common.FO4_DATA / common.ESMS[game]
    expected = json.loads((d / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if common.digest(installed) != expected:
        raise RuntimeError("Converted ESM changed")
    plans = list(common.PLAN_FILES[game]) + ["complete_sst_exact_migration_verified.jsonl.gz"]
    if game == "fo3":
        plans.append("ttw_foreign_master_text_verified.jsonl.gz")
    active = {}
    for name in plans:
        for row in common.rows(d / name):
            k = common.field_key(row)
            value = row["english"], row["korean"]
            if k in active and active[k] != value:
                raise RuntimeError(f"Existing plan has conflicting assignment: {k}")
            active[k] = value
    candidates = {}
    bodies = set()
    initial = Counter()
    for row in common.rows(d / "xtranslator_residual_candidates.jsonl.gz"):
        k = row["formid"], row["record_type"], row["field"], int(row["index"])
        if k in active or (row["record_type"], row["field"]) not in (
            ("INFO", "RNAM"), ("INFO", "NAM1")):
            continue
        if row["conditional_proc"] is not None or int(row["formid"], 16) >> 24 == 0:
            continue
        m = REGEX.fullmatch(row["english"])
        if not m:
            continue
        body = m.group("body")
        if not body or len(body) < 8:
            continue
        candidates[k] = (row, m.groupdict())
        bodies.add(body)
        initial[m.group("skill")] += 1

    # FO3 dictionaries are TTW-style: retain all FO3-named SST translations
    # even when MAST[0..5] are FNV. Never reinterpret those FNV local IDs as
    # FO3 native ESM IDs.
    source = defaultdict(set)
    translated = defaultdict(set)
    sst_sha = {}
    allowed_owners = {p + ".esm" for p in common.MASTERS[game]}
    foreign = set()
    if game == "fo3":
        foreign = {"falloutnv.esm", "deadmoney.esm", "honesthearts.esm",
                   "oldworldblues.esm", "lonesomeroad.esm", "gunrunnersarsenal.esm"}
    for plugin in common.MASTERS[game]:
        path = common.SST / (plugin + "_en_ko.sst")
        parsed = parser.parse_sst(path)
        sst_sha[path.name] = parsed["sha256"]
        masters = [name.casefold() for name in parsed["master_files"]]
        for row in parsed["records"]:
            english = row["source"]
            if english not in bodies or not row["korean"] or row["korean"] == english:
                continue
            f = int(row["form_id"], 16)
            if f >> 24 >= len(masters):
                continue
            owner = masters[f >> 24]
            if owner not in allowed_owners and owner not in foreign:
                continue
            translated[english].add(row["korean"])
            if (row["record_name"], row["field_name"]) not in NATIVE_FIELDS:
                continue
            source[english].add((
                row["korean"], path.name, owner, f & 0xFFFFFF,
                row["record_name"], row["field_name"], int(row["index"])
            ))

    # Native ESM record/field/English proof. For native-owner SST require
    # matching source FormID and field index. TTW FNV-owner SST cannot have a
    # direct FO3 ID, so use independent native FO3 text+field proof only.
    direct_ids = defaultdict(set)
    for english, entries in source.items():
        for _, _, owner, fid, typ, field, idx in entries:
            if owner in allowed_owners:
                direct_ids[owner].add(fid)
    direct_proof = defaultdict(set)
    any_original = defaultdict(set)
    orig_hashes = {}
    for plugin in common.MASTERS[game]:
        path = common.ORIGINAL[game] / (plugin + ".esm")
        owner_idx = native.original_owner_index(path)
        for fp, at, n, flags, fid, typ in fo3.records(path):
            if fid >> 24 != owner_idx or typ not in {"INFO", "DIAL"}:
                continue
            local = fid & 0xFFFFFF
            for field, idx, raw in fo3.fields(fo3.read_record(fp, at, n, flags)):
                if (typ, field) not in NATIVE_FIELDS:
                    continue
                value = fo3.decode(raw)
                if value not in bodies:
                    continue
                any_original[value].add((plugin + ".esm", local, typ, field, idx))
        orig_hashes[plugin + ".esm"] = common.digest(path)
    for english, entries in source.items():
        for row in entries:
            korean, sst_file, owner, local, typ, field, idx = row
            if owner in foreign:
                if any((s_typ, s_field) == (typ, field)
                       for _, _, s_typ, s_field, _ in any_original.get(english, ())):
                    direct_proof[english].add(row)
            elif (owner, local, typ, field, idx) in any_original.get(english, ()):
                direct_proof[english].add(row)

    translations = []
    reviews = []
    state = Counter()
    for key, (row, m) in candidates.items():
        body = m["body"]
        if len(translated.get(body, set())) != 1:
            reason = "source_sst_missing_or_translation_ambiguous"
        elif not direct_proof.get(body):
            reason = "no_original_native_esm_dialogue_source_proven"
        else:
            ko = next(iter(translated[body]))
            label = "[" + SKILLS[m["skill"]] + m["suffix"] + "]" + m["separator"]
            korean = label + ko
            if "\ufffd" in korean or not ko.strip():
                reason = "invalid_korean"
            elif Counter(common.TOKEN.findall(row["english"])) != Counter(common.TOKEN.findall(korean)):
                reason = "token_mismatch_after_localized_skill_label"
            else:
                reason = "source_sst_and_native_original_skill_dialogue_verified"
        state[reason] += 1
        if reason == "source_sst_and_native_original_skill_dialogue_verified":
            translations.append({
                "target_formid": key[0], "record_type": key[1], "field": key[2],
                "target_field_occurrence_index": key[3], "english": row["english"],
                "korean": korean,
                "plan_source": "converted_skill_label_plus_original_sst_dialogue",
                "label": m["skill"], "localized_label": SKILLS[m["skill"]],
                "source_english_body": body,
                "source_sst_evidence": [
                    {"ko_sst": sst_file, "source_owner": owner, "source_local_id": f"{fid:06X}",
                     "source_type": typ, "source_field": field, "source_field_index": idx}
                    for kor, sst_file, owner, fid, typ, field, idx in sorted(direct_proof[body])
                    if kor == ko
                ][:8],
                "runtime_context": "requires gameplay dialogue and token rendering QA",
            })
        else:
            reviews.append({
                "formid": key[0], "record_type": key[1], "field": key[2], "index": key[3],
                "english": row["english"], "source_body": body, "reason": reason,
                "sst_korean_unique": len(translated.get(body, set())),
            })
    # Verify targeted converted bytes before producing a patch assignment.
    byid = defaultdict(list)
    for row in translations:
        byid[int(row["target_formid"], 16)].append(row)
    found, visited = set(), set()
    for fid, typ, fields in native.esm_records(installed, set(byid)):
        if fid in visited:
            raise RuntimeError("Duplicate original converted record")
        visited.add(fid)
        for row in byid[fid]:
            key = common.field_key(row)
            if typ != row["record_type"] or fields.get((row["field"], row["target_field_occurrence_index"])) != row["english"]:
                raise RuntimeError(f"Wrong target byte content for {key}")
            if key in found:
                raise RuntimeError("Duplicate patch destination")
            found.add(key)
    if len(found) != len(translations) or common.digest(installed) != expected:
        raise RuntimeError("Target ESM changed or incomplete verification")
    translations.sort(key=common.field_key)
    common.out(d / "skill_prefix_verified.jsonl.gz", translations)
    common.out(d / "skill_prefix_review.jsonl.gz", reviews)
    report = {
        "game": game, "converted_esm_sha256": expected,
        "original_game_esm_sha256": orig_hashes, "sst_sha256": sst_sha,
        "eligible_known_skill_prefix_fields": len(candidates),
        "original_source_dialogue_with_body": len(any_original),
        "verified_new_fields": len(translations), "review_fields": len(reviews),
        "status": dict(state),
        "by_skill": dict(Counter(row["label"] for row in translations)),
        "warning": "Original SST and original ESM dialogue source proof, target bytes checked. Translation skill label is localized preserving Global/formatting tokens. No exact converter dialogue FormID mapping for these generated lines; in-game QA needed.",
    }
    (d / "skill_prefix_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(game, "SKILL NEW", len(translations), "REVIEW", len(reviews),
          "REASONS", dict(state), "LABELS", report["by_skill"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("game", choices=("fo3", "fnv"))
    run(parser.parse_args().game)
