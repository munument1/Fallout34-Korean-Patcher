"""Recover omitted QUST/NNAM quest objectives from the supplied complete SST.

The original migration whitelist omitted this PLAYER-VISIBLE field entirely.
Only exact source English + unique Korean is considered, backed by original
source ESM QUST/NNAM. Non-TTW entries also require exact plugin/FormID/index.
For FO3 TTW-source entries, source FormIDs belong to a different game: verify
the same English against the actual FO3 source ESM instead of equating IDs.

The target field/type/index/English and formatting tokens are independently
verified. Never generates or modifies any ESM, ESP, BA2, or installed files.
"""
from collections import Counter, defaultdict
import argparse
import json

import recover_complete_sst_exact_text as common
from translation_work_filter import classify

FIELD = ("QUST", "NNAM")
FILE = "quest_objective_native_sst_verified.jsonl.gz"
TTW = {
    "falloutnv.esm", "deadmoney.esm", "honesthearts.esm",
    "oldworldblues.esm", "lonesomeroad.esm", "gunrunnersarsenal.esm"
}


def run(game):
    native = common.module("quest_native", "recover_fnv_xtranslator_origin_verified.py")
    fo3 = common.module("quest_fo3", "recover_fo3_xtranslator_provenance.py")
    parser = common.module("quest_sst", "read_xtranslator_sst.py")
    outdir = common.ROOT / "data" / game
    target = common.FO4_DATA / common.ESMS[game]
    expected = json.loads((outdir / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if common.digest(target) != expected:
        raise RuntimeError("Converted target ESM SHA mismatch")

    files = list(common.PLAN_FILES[game]) + [
        "complete_sst_exact_migration_verified.jsonl.gz",
        "skill_prefix_verified.jsonl.gz",
    ]
    if game == "fo3":
        files.append("ttw_foreign_master_text_verified.jsonl.gz")
    else:
        files.extend(["editor_marker_verified.jsonl.gz", "inline_director_cues_verified.jsonl.gz"])
    planned = {}
    for name in files:
        for row in common.rows(outdir / name):
            k = common.field_key(row)
            value = row["english"], row["korean"]
            if k in planned and planned[k] != value:
                raise ValueError(f"Existing plan conflict {k}")
            planned[k] = value

    residual = {}
    for row in common.rows(outdir / "xtranslator_residual_candidates.jsonl.gz"):
        k = row["formid"].upper(), row["record_type"], row["field"], int(row["index"])
        if k not in planned and (row["record_type"], row["field"]) == FIELD and classify(row)[0] == "actionable":
            residual[k] = row
    remaining = {r["english"] for r in residual.values()}

    originals = defaultdict(set)
    all_korean = defaultdict(set)
    source_sha = {}
    supported = {s + ".esm" for s in common.MASTERS[game]}
    for source_name in common.MASTERS[game]:
        srcpath = common.SST / (source_name + "_en_ko.sst")
        parsed = parser.parse_sst(srcpath)
        source_sha[srcpath.name] = parsed["sha256"]
        masters = [s.casefold() for s in parsed["master_files"]]
        for row in parsed["records"]:
            en, ko = row["source"], row["korean"]
            if en not in remaining or not ko or ko == en:
                continue
            fid = int(row["form_id"], 16)
            if fid >> 24 >= len(masters):
                continue
            owner = masters[fid >> 24]
            if owner not in supported and not (game == "fo3" and owner in TTW):
                continue
            # Include all Korean variants for ambiguity detection, even when
            # a source variant originates in another record type.
            all_korean[en].add(ko)
            if (row["record_name"], row["field_name"]) == FIELD:
                originals[en].add((
                    ko, owner, fid & 0xFFFFFF, int(row["index"]), srcpath.name
                ))

    # Native-game evidence for the source quest objective text. This also
    # handles FO3 SST's imported TTW/master-index mapping without abusing
    # foreign FormIDs.
    native_originals = defaultdict(set)
    hashes = {}
    for source_name in common.MASTERS[game]:
        srcpath = common.ORIGINAL[game] / (source_name + ".esm")
        owner_index = native.original_owner_index(srcpath)
        for fd, at, size, flags, fid, rtype in fo3.records(srcpath):
            if rtype != FIELD[0] or fid >> 24 != owner_index:
                continue
            for field, index, raw in fo3.fields(fo3.read_record(fd, at, size, flags)):
                if field != FIELD[1]:
                    continue
                text = fo3.decode(raw)
                if text in remaining:
                    native_originals[text].add((srcpath.name.casefold(), fid & 0xFFFFFF, index))
        hashes[srcpath.name] = common.digest(srcpath)

    accepted = []
    deferred = []
    reasons = Counter()
    for key, row in residual.items():
        en = row["english"]
        variants = all_korean.get(en, set())
        orig = native_originals.get(en, set())
        proofs = []
        for ko, owner, local, idx, sstfile in originals.get(en, ()):
            if game == "fo3" and owner in TTW:
                # TTW local FormID is not a Fallout3 local FormID.
                matched = sorted(orig)
                origin_mode = "ttw_english_verified_against_fo3_native_quest_objective"
            else:
                matched = sorted(q for q in orig if q == (owner, local, idx))
                origin_mode = "exact_original_plugin_formid_and_field_index"
            for original in matched[:4]:
                proofs.append({
                    "korean": ko, "sst": sstfile, "sst_owner": owner,
                    "sst_formid_local": f"{local:06X}", "sst_field_index": idx,
                    "native_original_quest": {
                        "plugin": original[0], "formid_local": f"{original[1]:06X}",
                        "field_index": original[2]
                    },
                    "origin_mode": origin_mode,
                })

        if len(variants) != 1:
            reason = "no_unique_sst_korean"
        elif not proofs:
            reason = "no_native_source_sst_matching_provenance"
        else:
            ko = next(iter(variants))
            if not ko.strip() or "\ufffd" in ko or Counter(common.TOKEN.findall(en)) != Counter(common.TOKEN.findall(ko)):
                reason = "bad_korean_or_protected_token_mismatch"
            elif any(p["korean"] != ko for p in proofs):
                reason = "inconsistent_sst_proof"
            else:
                reason = "native_quest_objective_and_sst_verified"
        reasons[reason] += 1
        if reason == "native_quest_objective_and_sst_verified":
            accepted.append({
                "target_formid": key[0], "record_type": key[1], "field": key[2],
                "target_field_occurrence_index": key[3],
                "english": en, "korean": ko,
                "plan_source": "original_game_quest_objective_sst_verified",
                "source_evidence": proofs[:8],
                "source_evidence_count": len(proofs),
                "verification_note": "Original QUST/NNAM text and unique Korean SST verified. Ported quest target runtime identity not proven.",
            })
        else:
            deferred.append({
                "target_formid": key[0], "record_type": key[1], "field": key[2],
                "target_field_occurrence_index": key[3], "english": en,
                "reason": reason, "sst_korean_variants": len(variants),
                "native_original_matches": len(orig)
            })

    # Independently check every proposed assignment in converted ESM.
    grouped = defaultdict(list)
    for row in accepted:
        grouped[int(row["target_formid"], 16)].append(row)
    found = set()
    for fid, rtype, decoded in native.esm_records(target, set(grouped)):
        for row in grouped[fid]:
            k = common.field_key(row)
            if k in found or rtype != row["record_type"] or decoded.get((row["field"], row["target_field_occurrence_index"])) != row["english"]:
                raise ValueError(f"Converted ESM field mismatch: {k}")
            found.add(k)
    if len(found) != len(accepted) or common.digest(target) != expected:
        raise RuntimeError("Converted ESM changed, or proposed fields not fully verified")
    accepted.sort(key=common.field_key)
    common.out(outdir / FILE, accepted)
    common.out(outdir / "quest_objective_native_sst_review.jsonl.gz", deferred)
    report = {
        "game": game, "newly_linked": len(accepted), "review": len(deferred),
        "classification": dict(reasons), "target_esm_sha256": expected,
        "source_game_esm_sha256": hashes, "source_game_sst_sha256": source_sha,
        "warning": "Original ESM/SST and target ESM static verified, target quest runtime identity not independently proven. No installed assets modified."
    }
    (outdir / "quest_objective_native_sst_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(game, "QUEST_LINKED", len(accepted), "REVIEW", len(deferred), "REASONS", dict(reasons), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("game", choices=("fo3", "fnv"))
    run(p.parse_args().game)
