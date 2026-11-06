"""Recover still missing screen fields from original ESM-verified SST entries.

This is an extension of the verified-plan translation memory: source Korean
can be present in native game's ESM/SST but the original record type is a
different, semantically compatible player-display role in the FO4 conversion.

Only whole-English exact matching and single Korean translation across all
relevant original complete SST sources. All non-TTW citations must match the
original ESM's plugin, FormID, type, field, subrecord index and English; FO3
TTW cross-master entries are independently cross-checked against the actual
original FO3 ESM text+type+field. Target ESM fields and placeholders are exact.
No game assets are written. Target context/in-game semantics remain QA work.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import json

import recover_complete_sst_exact_text as common
from recover_original_quest_objectives import FILE as QUEST_FILE
from recover_verified_plan_translation_memory import FILE as MEM_FILE, PAIR
from translation_work_filter import classify

FILE = "native_sst_semantic_copy_verified.jsonl.gz"
TTW = {
    "falloutnv.esm", "deadmoney.esm", "honesthearts.esm",
    "oldworldblues.esm", "lonesomeroad.esm", "gunrunnersarsenal.esm",
}


def current_plans(game):
    names = list(common.PLAN_FILES[game]) + [
        "complete_sst_exact_migration_verified.jsonl.gz", "skill_prefix_verified.jsonl.gz",
        QUEST_FILE, MEM_FILE,
    ]
    if game == "fo3":
        names.append("ttw_foreign_master_text_verified.jsonl.gz")
    else:
        names.extend(["editor_marker_verified.jsonl.gz", "inline_director_cues_verified.jsonl.gz",
                      "punctuation_normalized_verified.jsonl.gz"])
    return names


def run(game):
    native = common.module("native_sem", "recover_fnv_xtranslator_origin_verified.py")
    fo3 = common.module("fo3_sem", "recover_fo3_xtranslator_provenance.py")
    read = common.module("sst_sem", "read_xtranslator_sst.py")
    d = common.ROOT / "data" / game
    target = common.FO4_DATA / common.ESMS[game]
    expected = json.loads((d / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if common.digest(target) != expected:
        raise ValueError(f"{game}: source ESM SHA mismatch")

    planned = {}
    for name in current_plans(game):
        for row in common.rows(d / name):
            key = common.field_key(row)
            pair = row["english"], row["korean"]
            if key in planned and planned[key] != pair:
                raise ValueError(f"Existing plan conflict {key}")
            planned[key] = pair
    residual = {}
    wanted = set()
    for row in common.rows(d / "xtranslator_residual_candidates.jsonl.gz"):
        key = row["formid"].upper(), row["record_type"], row["field"], int(row["index"])
        if key in planned or classify(row)[0] != "actionable":
            continue
        if key[1:3] not in PAIR:
            continue
        residual[key] = row
        wanted.add(row["english"])

    kos = defaultdict(set)
    possible = defaultdict(set)
    source_hashes = {}
    allowed = {s + ".esm" for s in common.MASTERS[game]}
    for part in common.MASTERS[game]:
        sstpath = common.SST / (part + "_en_ko.sst")
        parsed = read.parse_sst(sstpath)
        source_hashes[sstpath.name] = parsed["sha256"]
        master_list = [v.casefold() for v in parsed["master_files"]]
        for row in parsed["records"]:
            en, ko = row["source"], row["korean"]
            if en not in wanted or not ko or en == ko:
                continue
            form = int(row["form_id"], 16)
            if form >> 24 >= len(master_list):
                continue
            owner = master_list[form >> 24]
            if owner not in allowed and not (game == "fo3" and owner in TTW):
                continue
            kos[en].add(ko)
            source_pair = row["record_name"], row["field_name"]
            if not any(source_pair in PAIR[p] for p in PAIR):
                continue
            possible[(en, source_pair)].add((
                ko, owner, form & 0xFFFFFF, int(row["index"]), sstpath.name
            ))

    # Source evidence: exact original English, native record/field and source
    # ownership; don't treat TTW foreign master FormIDs as FO3 identifiers.
    original = defaultdict(set)
    hashes = {}
    wantedpairs = set(possible)
    sourcetypes = {p[1][0] for p in wantedpairs}
    for part in common.MASTERS[game]:
        src = common.ORIGINAL[game] / (part + ".esm")
        owner_idx = native.original_owner_index(src)
        for fp, at, size, flags, fid, typ in fo3.records(src):
            if fid >> 24 != owner_idx or typ not in sourcetypes:
                continue
            local = fid & 0xFFFFFF
            for field, idx, raw in fo3.fields(fo3.read_record(fp, at, size, flags)):
                en = fo3.decode(raw)
                if (en, (typ, field)) in wantedpairs:
                    original[(en, (typ, field))].add((src.name.casefold(), local, idx))
        hashes[src.name] = common.digest(src)

    verified, rejected = [], []
    reasons = Counter()
    byfield = Counter()
    for key, row in residual.items():
        en = row["english"]
        pairs = PAIR[key[1:3]]
        evidence = []
        for sourcepair in pairs:
            for ko, owner, local, index, sst in possible.get((en, sourcepair), ()):
                candidates = original.get((en, sourcepair), set())
                for srcname, srcid, srcidx in candidates:
                    ttw = game == "fo3" and owner in TTW
                    if not ttw and (owner, local, index) != (srcname, srcid, srcidx):
                        continue
                    evidence.append((
                        ko, sst, owner, local, index, sourcepair[0], sourcepair[1],
                        srcname, srcid, srcidx, ttw
                    ))
        if len(kos.get(en, set())) != 1:
            status = "source_SST_absent_or_conflicting_Korean"
        elif not evidence:
            status = "no_original_native_ESM_SST_provenance_for_compatible_field"
        else:
            ko = next(iter(kos[en]))
            if not ko.strip() or "\ufffd" in ko or Counter(common.TOKEN.findall(en)) != Counter(common.TOKEN.findall(ko)):
                status = "invalid_korean_or_protected_tokens"
            elif any(v[0] != ko for v in evidence):
                status = "source_sst_evidence_disagrees"
            else:
                status = "original_game_semantic_sst_link_verified"
        reasons[status] += 1
        if status == "original_game_semantic_sst_link_verified":
            byfield[key[1] + "/" + key[2]] += 1
            verified.append({
                "target_formid": key[0], "record_type": key[1], "field": key[2],
                "target_field_occurrence_index": key[3], "english": en, "korean": ko,
                "plan_source": "native_original_game_esm_sst_semantic_field_crossmatch",
                "source_evidence": [
                    {
                        "sst": sst, "sst_master": owner,
                        "sst_formid_local": f"{local:06X}", "sst_index": index,
                        "source_record": f"{typ}:{field}",
                        "original_esm": srcname, "original_formid_local": f"{fid:06X}",
                        "original_index": idx, "ttw_foreign_master": is_ttw,
                    }
                    for kko, sst, owner, local, index, typ, field, srcname, fid, idx, is_ttw
                    in sorted(set(evidence))[:8]
                ],
                "source_evidence_count": len(set(evidence)),
                "verification_note": "Exact original ESM/SST source & target bytes verified, but FO4-converted runtime context still unproven.",
            })
        elif evidence:
            rejected.append({
                "target_formid": key[0], "record_type": key[1], "field": key[2],
                "index": key[3], "english": en, "reason": status,
                "available_korean_variants": len(kos.get(en, set())),
                "matching_sources": len(evidence),
            })

    source_ids = defaultdict(list)
    for r in verified:
        source_ids[int(r["target_formid"], 16)].append(r)
    found = set()
    for fid, typ, decoded in native.esm_records(target, set(source_ids)):
        for r in source_ids[fid]:
            key = common.field_key(r)
            if key in found or typ != key[1] or decoded.get((key[2], key[3])) != r["english"]:
                raise ValueError(f"Original converted target changed for {key}")
            found.add(key)
    if len(found) != len(verified) or common.digest(target) != expected:
        raise ValueError("Not all target ESM fields verified or game asset changed")
    common.out(d / FILE, sorted(verified, key=common.field_key))
    common.out(d / "native_sst_semantic_copy_review.jsonl.gz", rejected)
    report = {
        "game": game, "newly_verified_fields": len(verified),
        "by_target_field": dict(byfield), "classification": dict(reasons),
        "review_evidence_rows": len(rejected), "esm_sha256": expected,
        "original_source_esm_sha256": hashes, "sst_sha256": source_hashes,
        "warning": "Strict original ESM + complete SST exact-text semantics, not proof of the target record's speaker/quest runtime identity. Original ESM/ESP unchanged."
    }
    (d / "native_sst_semantic_copy_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(game, "NATIVE_SST_SEMANTIC_NEW", len(verified), "BY_FIELD", dict(byfield), "REASONS", dict(reasons), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("game", choices=("fo3", "fnv"))
    run(p.parse_args().game)
