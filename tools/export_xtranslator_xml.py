"""Export current verified Fallout34 translation plans as xTranslator XML.

Reproduces the xTranslator SSTXMLRessources v2 layout observed in an actual
xTranslator-exported file (Params/Addon, Content/String List, EDID, REC,
Source, Dest). Source/target are UTF-8. Repeated subrecord occurrences receive
REC id (1-based) and idMax. Source CR is XML-escaped as &#13; to preserve CRLF.

Two XMLs are generated per converted ESM:
  * *_en_ko.xml: safe-to-review default; excludes *globally ambiguous English*
    that has multiple Korean translations in otherwise verified field plans.
  * *_CONTEXT_REVIEW.xml: context-sensitive assignments only; NEVER bulk
    import this XML with source-only matching.

The record field bytes are reverified against the pinned installed ESM, but
installed files are NEVER written. This is NOT an ESM builder and does not
establish in-game reachability or context correctness. The generated XMLs
are for xTranslator import/review, not directly usable runtime localization.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from build_localized_esm_copy import load_assignments, read_plain_string
from report_remaining_esm_translation_gaps import PLANS, MIGRATED_PLANS
from verify_localized_esm_copy import events, subrecords
from recover_complete_sst_exact_text import ROOT, FO4_DATA, TOKEN, digest

OUTPUT = ROOT / "dist" / "xtranslator"
TARGETS = {"fo3": "Fallout34.esm", "fnv": "FalloutNV34.esm"}
APP_EXTRAS = (
    "xtranslator_verified_visible_extra.jsonl.gz",
    "manual_visible_translation_verified.jsonl.gz",
    "sibling_info_field_verified.jsonl.gz",
)
INVALID_XML = lambda c: not (
    c == "\x09" or c == "\x0a" or c == "\x0d" or
    "\x20" <= c <= "\uD7FF" or
    "\uE000" <= c <= "\uFFFD" or
    "\U00010000" <= c <= "\U0010FFFF"
)


def xml_text(text: str) -> str:
    """XML 1.0 escaping preserving carriage returns for exact source match."""
    if any(INVALID_XML(c) for c in text):
        raise ValueError("An XML 1.0 forbidden character was encountered")
    return escape(text).replace("\r", "&#13;")


def write_header(stream, plugin_name: str):
    stream.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
    stream.write("<SSTXMLRessources>\n  <Params>\n")
    stream.write(f"    <Addon>{xml_text(plugin_name)}</Addon>\n")
    stream.write("    <Source>en</Source>\n    <Dest>ko</Dest>\n")
    stream.write("    <Version>2</Version>\n  </Params>\n  <Content>\n")


def write_entry(stream, edid: str, rtype: str, field: str, field_idx: int,
                max_field: int, english: str, korean: str):
    stream.write('    <String List="0">\n')
    stream.write(f"      <EDID>{xml_text(edid)}</EDID>\n")
    if max_field > 1:
        stream.write(
            f'      <REC id="{field_idx + 1}" idMax="{max_field}">'
            f"{rtype}:{field}</REC>\n"
        )
    else:
        stream.write(f"      <REC>{rtype}:{field}</REC>\n")
    stream.write(f"      <Source>{xml_text(english)}</Source>\n")
    stream.write(f"      <Dest>{xml_text(korean)}</Dest>\n")
    stream.write("    </String>\n")


def write_footer(stream):
    stream.write("  </Content>\n</SSTXMLRessources>\n")


def extract(game: str, workdir: Path):
    from collections import defaultdict
    from hashlib import sha256

    folder = ROOT / "data" / game
    plugin = TARGETS[game]
    esm = FO4_DATA / plugin
    expected = json.loads((folder / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if digest(esm) != expected:
        raise RuntimeError(f"{game}: pinned ESM SHA changed")
    # The same files and ordering used by the exact target ESM verifier.
    plans, by_source = load_assignments(
        folder, [folder / file for file in (*APP_EXTRAS, *MIGRATED_PLANS[game])]
    )
    counter = Counter()
    translations = defaultdict(set)
    for (fid, typ, field, idx), (en, ko) in plans.items():
        if Counter(TOKEN.findall(en)) != Counter(TOKEN.findall(ko)):
            raise ValueError(f"format tokens differ at {fid:08X}:{typ}:{field}:{idx}")
        translations[en].add(ko)
    ambiguous = {en for en, vals in translations.items() if len(vals) > 1}

    # Streaming avoids loading the 350-370 MB ESM or hundreds of thousands of
    # XML nodes in memory. Match exact record, field, index and English bytes.
    safe = workdir / f"{Path(plugin).stem}_en_ko.xml"
    review = workdir / f"{Path(plugin).stem}_CONTEXT_REVIEW.xml"
    text_review = workdir / f"{Path(plugin).stem}_CONTEXT_REVIEW.tsv"
    allowed = {(fid, typ) for fid, typ, field, idx in plans}
    seen = set()
    skipped_invalid = []
    with safe.open("w", encoding="utf8", newline="\n") as good, \
         review.open("w", encoding="utf8", newline="\n") as review_xml, \
         text_review.open("w", encoding="utf-8-sig", newline="") as review_txt:
        write_header(good, plugin)
        write_header(review_xml, plugin)
        csvw = csv.writer(review_txt, delimiter="\t")
        csvw.writerow(["formid", "type", "field", "index", "english", "korean", "reason"])
        for ev in events(esm):
            if ev[0] != "record":
                continue
            (tag, fid, _, _, _), content = ev[1], ev[2]
            typ = tag.decode("ascii", "replace")
            if (fid, typ) not in allowed:
                continue
            decoded_fields = list(subrecords(content))
            totals = Counter(field for (field, idx), raw in decoded_fields)
            edid = None
            for (field, idx), raw in decoded_fields:
                if field == "EDID":
                    value = read_plain_string(raw)
                    if value and not any(INVALID_XML(c) for c in value):
                        edid = value
                    break
            if not edid:
                edid = f"[{fid:08X}]"
                counter["fallback_bracket_formid_edid"] += 1
            for (field, idx), raw in decoded_fields:
                k = fid, typ, field, idx
                if k not in plans:
                    continue
                if k in seen:
                    raise RuntimeError(f"Duplicate planned target {k}")
                seen.add(k)
                en, ko = plans[k]
                if read_plain_string(raw) != en:
                    raise RuntimeError(f"ESM source text changed for {k}")
                if any(INVALID_XML(c) for c in en + ko):
                    skipped_invalid.append(f"{fid:08X}:{typ}:{field}:{idx}")
                    counter["xml_1_0_illegal_text_skipped"] += 1
                    continue
                if en in ambiguous:
                    write_entry(review_xml, edid, typ, field, idx, totals[field], en, ko)
                    csvw.writerow([f"{fid:08X}", typ, field, idx, en, ko, "ambiguous_same_english_different_korean"])
                    counter["review_context_sensitive"] += 1
                else:
                    write_entry(good, edid, typ, field, idx, totals[field], en, ko)
                    counter["safe_xml_entries"] += 1
        write_footer(good)
        write_footer(review_xml)
    if len(seen) != len(plans):
        raise RuntimeError(f"ESM lacks {len(plans)-len(seen)} planned fields")
    if digest(esm) != expected:
        raise RuntimeError("ESM changed during XML export")

    # Parse the real XML files, not just string-check the writer.
    for path, count in ((safe, counter["safe_xml_entries"]), (review, counter["review_context_sensitive"])):
        actual = 0
        for _, elem in ET.iterparse(path, events=("end",)):
            if elem.tag == "String":
                if not elem.findtext("Source") or not elem.findtext("Dest"):
                    raise ValueError(f"{path}: missing Source or Dest")
                actual += 1
                elem.clear()
        if actual != count:
            raise RuntimeError(f"{path}: XML parse returned {actual} expected {count}")

    stat = {
        "game": game, "plugin": plugin, "esm_sha256": expected,
        "planned_target_field_occurrences": len(plans),
        "safe_xml_rows": counter["safe_xml_entries"],
        "context_review_xml_rows": counter["review_context_sensitive"],
        "distinct_english_with_ambiguous_korean": len(ambiguous),
        "invalid_xml_rows_excluded": counter["xml_1_0_illegal_text_skipped"],
        "fallback_formid_edid_records": counter["fallback_bracket_formid_edid"],
        "xml_sha256": {
            p.name: digest(p) for p in (safe, review)
        },
        "verified_source_plan_counts": dict(by_source),
        "import_note": "Load the matching converted ESM in xTranslator Fallout4 mode. Use Import Translation -> XML; preview matches. Context-review XML MUST NOT be mass-imported by English string only. Data was not in-game QA tested. No installed ESM changed.",
    }
    (workdir / f"{Path(plugin).stem}_XML_report.json").write_text(
        json.dumps(stat, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    if skipped_invalid:
        (workdir / f"{Path(plugin).stem}_XML_skipped.json").write_text(
            json.dumps(skipped_invalid, indent=2) + "\n", encoding="utf8"
        )
    print(game, "XML_CREATED", dict(counter), "SHA", expected, flush=True)
    return stat


def run():
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", type=Path, default=ROOT / "work" / "xtranslator")
    p.add_argument("--output", type=Path, default=OUTPUT)
    p.add_argument("--games", nargs="+", choices=("fo3", "fnv"), default=("fo3", "fnv"))
    args = p.parse_args()
    wd = args.workdir.resolve()
    wd.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = [extract(game, wd) for game in args.games]
    notes = (
        "Fallout34 한국어판 — xTranslator XML 번역 가져오기\n"
        "=============================================\n"
        "1. xTranslator를 Fallout 4 게임 모드로 실행하세요.\n"
        "2. XML의 Addon과 같은 이름의 Fallout34.esm 또는 FalloutNV34.esm을 엽니다.\n"
        "3. 파일(File) -> 번역 가져오기(Import Translation) -> XML 파일로\n"
        "   해당 게임의 *_en_ko.xml을 하나씩 불러옵니다.\n"
        "4. 가급적 레코드/FormID 참조 기반으로 가져오고, 적용 미리보기를 검사하세요.\n"
        "   영어가 동일하다는 이유로 모든 문구를 무조건 덮어쓰면 안 됩니다.\n"
        "5. *_CONTEXT_REVIEW.xml은 같은 영문에 서로 다른 검증 번역이 존재하는\n"
        "   특수 항목입니다. 일괄 가져오지 말고 레코드별로 수동 확인하세요.\n"
        "   같은 이름의 *_CONTEXT_REVIEW.tsv에서 각 FormID를 확인할 수 있습니다.\n"
        "6. 이번 패키지는 번역용 XML이지 게임에 바로 설치하는 한글 ESM이 아닙니다.\n"
        "   게임에 설치된 ESM/ESP/BA2 및 온라인 모드는 변경하지 않았습니다.\n"
        "7. 연결 수는 정적 필드 계획이며 인게임 번역 완성을 증명하지 않습니다.\n"
        "   데이터 원본은 각 *_XML_report.json의 ESM SHA256에 고정되어 있습니다.\n"
        "8. 폴아웃 4 본편·DLC·CC 한국어판/폰트는 이 ZIP에 포함되지 않습니다.\n"
        "   Fallout34 포팅 ESM 두 개의 한국어 사전만 수록했습니다.\n"
    )
    (wd / "README_IMPORT.txt").write_text(notes, encoding="utf8")
    result_file = args.output / "Fallout34_FO3_FNV_xTranslator_Korean_XML.zip"
    files = [
        p for p in sorted(wd.iterdir())
        if p.is_file() and (
            p.name == "README_IMPORT.txt"
            or any(p.name.startswith(Path(TARGETS[g]).stem + "_") for g in args.games)
        )
    ]
    with zipfile.ZipFile(result_file, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as z:
        for path in files:
            z.write(path, path.name)
    with zipfile.ZipFile(result_file) as z:
        corrupt = z.testzip()
        if corrupt:
            raise RuntimeError(f"ZIP member CRC mismatch {corrupt}")
    summary = {
        "format": "xTranslator SSTXMLRessources XML v2",
        "zip_name": result_file.name,
        "zip_size_bytes": result_file.stat().st_size,
        "zip_sha256": digest(result_file),
        "files": [p.name for p in files],
        "games": manifest,
        "warning": "XML syntax round-trip validated, not yet imported in xTranslator GUI or tested in game.",
    }
    (args.output / "Fallout34_xTranslator_XML_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print("ZIP_CREATED", result_file, "BYTES", summary["zip_size_bytes"], "SHA", summary["zip_sha256"])


if __name__ == "__main__":
    run()
