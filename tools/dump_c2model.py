#!/usr/bin/env python3
"""Dump and label C2MODEL.DAT (Caesar II 1.1A).

File is 4360 bytes = 1090 little-endian int32s. No magic, no records of one
stride. Tables are packed back-to-back with zero-run padding.

Labels with confidence high/medium are evidence from this file (exact FAQ
sequences or internal consistency). Wiki/manual numbers that do *not* appear
are listed as ABSENT, not as facts.

Do not copy C2MODEL.DAT into git. JSON/markdown exports are numbers + labels.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter
from pathlib import Path

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")

DIFFICULTIES = ("Novice", "Easy", "Normal", "Hard", "Impossible")
RANKS_10 = (
    "Citizen",
    "Decurion",
    "Apparitor",
    "Magistrate",
    "Quaestor",
    "Procurator",
    "Aedile",
    "Praetor",
    "Proconsul",
    "Consul",
)
HOUSE_GRADES = (
    "One hut",
    "Two huts",
    "Three huts",
    "Communal hut",
    "Large communal hut",
    "Primitive house",
    "Simple house",
    "Small house",
    "Average house",
    "Improved house",
    "Large house",
    "Grand house",
    "Primitive insula",
    "Simple insula",
    "Small insula",
    "Average insula",
    "Improved insula",
    "Large insula",
    "Grand insula",
    "Imperial insula",
    "Simple domus",
    "Small domus",
    "Average domus",
    "Improved domus",
    "Large domus",
    "Grand domus",
    "Simple villa",
    "Small villa",
    "Improved villa",
    "Grand villa",
    "Small palace",
    "Large palace",
)

# FAQ v1.0 sequences (caesar2.com / Falanx). Install is 1.1A.
FAQ_SEQ = {
    "difficulty_starting_money": [20000, 15000, 12000, 7000, 5000],
    "difficulty_promotions": [5, 7, 10, 15, 20],
    "rank_individual_pct": [20, 25, 30, 35, 40, 45, 50, 55, 60, 65],
    "rank_average_pct": [30, 35, 40, 45, 50, 55, 60, 65, 70, 74],
    "house_land_value_required": [
        0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30,
        32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 54, 54, 56, 58, 60, 64,
    ],
    "house_occupancy": [
        2, 4, 6, 8, 10, 12, 6, 7, 8, 9, 12, 16, 20, 24, 28, 32,
        36, 42, 48, 54, 20, 25, 30, 35, 40, 45, 100, 120, 150, 200, 300, 500,
    ],
    "city_building_costs_faq_order": [
        20, 50, 15, 30, 300, 500, 700, 1000, 1500, 2500, 250, 500,
        20, 75, 5, 80, 200, 600, 3, 12, 100, 400, 1500, 100, 400, 40, 80, 500, 1000,
    ],
    "entertainment_costs": [300, 500, 700, 1000, 1500, 2500],
    "worship_costs": [80, 200, 600],
    "province_costs": [20, 50, 500, 100, 250, 1000, 150, 400, 500],
    "pop_unlocks": [400, 800, 1200, 1800, 2400, 4800],
    "worship_pop_shrine": [500, 2000, 5000],
    "worship_pop_temple": [1000, 4000, 10000],
    "worship_pop_basilica": [1500, 6000, 15000],
    "lv_evolve_grades": [17, 33, 49],
    "business_lv_caps": [10, 16, 26],
    "imperial_tax_brackets": [8000, 5000, 3000],
    "forum_aventine_lv": [2, 2, 3, 2, 4, 2, 5, 3],
    "forum_janiculan_lv": [3, 2, 4, 2, 5, 3, 6, 3],
    "forum_palatine_lv": [3, 2, 4, 3, 5, 3, 6, 4],
    "shrine_lv": [5, 2, 6, 2, 7, 3, 8, 3],
    "temple_lv": [6, 2, 7, 3, 8, 3, 9, 4],
    "basilica_lv": [7, 3, 8, 3, 9, 4, 10, 4],
    "bath_lv": [3, 3, 4, 3, 5, 3, 6, 3],
}

# (start, end_exclusive, id, confidence, title)
# confidence: high | medium | low | pad | unknown
RANGES: list[tuple[int, int, str, str, str]] = [
    (0, 5, "diff_param_a", "medium",
     "5 difficulty scalars 20,15,10,5,2 (Novice->Impossible). Meaning opaque "
     "(not promotion counts 5,7,10,15,20 -- those are ABSENT)."),
    (5, 10, "diff_starting_money", "high",
     "Starting city funds Novice->Impossible: 20000,15000,12000,7000,5000."),
    (10, 15, "diff_money_b", "medium",
     "5 difficulty money scalars 2000,500,250,150,100. Hypothesis: per-province "
     "cut / stipend / gift band (FAQ v1.0 says -250 flat -- not stored here)."),
    (15, 35, "lv_caps_5x4", "low",
     "20 ints = 5x4 decreasing rows (10,16,24,35 / 8,14,20,30 / ...). "
     "Hypothesis: land-value ceilings at 4 radii (FAQ business caps 10,16,26 "
     "are ABSENT; 26 is not in the file)."),
    (35, 55, "opaque_5x4", "low",
     "20 ints, 5x4-ish. No FAQ hit."),
    (55, 75, "diff_pct_5x4", "medium",
     "5 difficulties x 4 percentages: Novice/Easy 50,60,80,90; then "
     "45,55,75,85 / 40,50,70,80 / 30,45,60,75. Hypothesis: rating leniency "
     "or event thresholds (4 categories)."),
    (75, 95, "diff_event_5x4", "medium",
     "5 difficulties x 4 scalars: (10,20,60,1) x2, then (8,20,48,1), "
     "(6,25,36,3), (4,25,24,7). Hypothesis: event timing / severity."),
    (95, 96, "gap_95", "unknown", "Single 0 between event records and cost list."),
    (96, 102, "city_sec_water_costs", "medium",
     "1, 5, 20, 40, 75, 50. 5=gateway, 20=city wall, 75=tower, 50=reservoir "
     "(FAQ). 1 and 40 unlabeled."),
    (102, 115, "city_build_costs", "medium",
     "Gardens 3, Plaza 12, Well 20, Baths 30, Hospital-or-Rhetor 500, "
     "Fountain 15, Barracks-or-Janiculan 400, Prefecture-or-Aventine 100, "
     "Market 40, Business 80, Grammaticus 250, Rhetor-or-Hospital 500, "
     "Library 1000. Grouped by family, not FAQ water->... order."),
    (115, 118, "worship_costs", "high",
     "Shrine 80, Temple 200, Basilica 600."),
    (118, 124, "entertainment_costs", "high",
     "Theater 300, Odeum 500, Arena 700, Coliseum 1000, Circus 1500, "
     "Circus Maximus 2500."),
    (124, 157, "scale_0_160_step5", "high",
     "0,5,10,...,160 (33 entries). Rank 20...65 at [128] is a subsequence of "
     "this ramp -- coincidence, not the rank table."),
    (157, 165, "pad_157", "pad", "8 zeros after the 0...160 ramp."),
    (165, 175, "money_ladder_10", "medium",
     "100,150,200,300,400,500,700,1000,1500,2500. 10-step money ladder "
     "(rank tribute / gift / building-tier -- not unique to one FAQ list)."),
    (175, 196, "pad_175", "pad", "21 zeros before province costs."),
    (196, 197, "gardens_cost_dup", "medium",
     "3 = Gardens (also at [102]). Leads the province-cost block."),
    (197, 206, "province_costs", "high",
     "Road 20, Wall 50, Fort 500, Work camp 100, Farm/Mine/Quarry 250, "
     "Port 1000, Warehouse 150, Shipyard 400, Trading post 500."),
    (206, 215, "pad_206", "pad", "9 zeros before housing occupancy."),
    (215, 247, "house_occupancy", "high",
     "32 housing grades, occupancy exact FAQ (One hut=2 ... Large palace=500)."),
    (247, 279, "house_tax_wealth", "high",
     "32 ints after occupancy. Per-person jump Imperial insula 58/54~1.07 vs "
     "Simple domus 64/20=3.2 matches FAQ ~3x tax at that evolution. "
     "Annual tax/wealth per house, not required land value (that sequence "
     "is ABSENT; the 0,2,4,6,8 hit at [214] is pad+occupancy)."),
    (279, 326, "curve_signed_47", "medium",
     "47-entry signed curve 10...-16...0. Lookup vs a 0...46 index "
     "(unrest / favor / peace -- not identified)."),
    (326, 378, "curve_signed_52", "medium",
     "52-entry signed curve 10...-20...100. Sister of [279:326], then climbs."),
    (378, 404, "tax_rate_lookup_26", "medium",
     "26 entries -2...40 saturating. Index = tax% 0...25 fits FAQ do-not-raise "
     "above 7-8% (values jump 10,15,20 from index 7). Unrest or LV penalty."),
    (404, 436, "house_signed_32", "medium",
     "32 signed ints +3...-12 by housing grade (need / decay / fire -- opaque)."),
    (436, 500, "sentinel9_64", "low",
     "64 small ints, 9 is common (n/a?). 32 pairs. Possible extra housing "
     "service flags. No exact FAQ sequence."),
    (500, 564, "house_lv_bonus_radius", "high",
     "32 (bonus,radius) pairs for housing: slums (-2,1)x3 ... villas (8,2)x4, "
     "palaces (16,2)x2. Radius 1 for 1-tile grades, 2 for 2x2/3x3."),
    (564, 612, "forum_worship_lv", "high",
     "Exact FAQ land-value (bonus,radius) grades: Aventine 2;2...5;3, "
     "Janiculan 3;2...6;3, Palatine 3;2...6;4, Shrine 5;2...8;3, Temple 6;2...9;4, "
     "Basilica 7;3...10;4."),
    (612, 617, "pad_612", "pad", "5 zeros after worship land-value pairs."),
    (617, 732, "pct_5tuples", "low",
     "23x5 ints. Many rows sum 80-100. First row 5,0,0,80,0 may be a header. "
     "Hypothesis: mix/weights (culture or goods). Not province count."),
    (732, 790, "other_lv_bonus_radius", "high",
     "29 (bonus,radius) pairs. Confirmed: Odeum 3;4, Coliseum 4;5, Plaza 4;1, "
     "Baths 3;3...6;3. Also Theater/Fountain-like 2;2 and 3;2, Market 2;1."),
    (790, 890, "rank_individual", "high",
     "5 difficulties x 20 rank slots, individual rating %. 99 = unused slot "
     "(Novice 5 ranks, Easy 7). Normal pads with 65; Hard with 82; "
     "Impossible fills all 20 (25...94). FAQ v1.0 listed 10 ranks only."),
    (890, 990, "rank_average", "high",
     "Same 5x20 layout for average rating %. Novice 25...45; Normal 30...74 "
     "padded; Impossible 35...97."),
    (990, 1010, "rank_pair_7_40", "medium",
     "10 x (7, 40). One pair per FAQ rank. Units unknown (not walker 36/28)."),
    (1010, 1016, "pleb_walker_scalars", "low",
     "7,20,80,40,20,4. 20 matches construction-pleb crew (FAQ). 4 matches "
     "common walker period (months). Rest unlabeled."),
    (1016, 1020, "pad_1016", "pad", "4 zeros before imperial tax brackets."),
    (1020, 1023, "imperial_tax_brackets", "high",
     "8000, 5000, 3000 = Caesar personal-savings tax bands (FAQ: 8000+ / "
     "5000-7999 / 3000-4999). Percents 10/19/26 are ABSENT."),
    (1023, 1024, "workcamp_plebs", "medium",
     "30 = plebs per work camp (FAQ)."),
    (1024, 1083, "default_tens", "low",
     "59 ints, almost all 10, one 20 at [1043]. Per-type default?"),
    (1083, 1090, "tail_signed", "low",
     "3,1,-3,-1,4,2,-1. Leftover signed 7. Not FAQ goal-shift -1,-1,0,+1,+1."),
]

ABSENT_FAQ = (
    "difficulty_promotions 5,7,10,15,20",
    "required land value 0,2,4,...,64 (false partial at [214])",
    "city costs in FAQ water->sanitation order",
    "pop unlocks 400,800,1200,1800,2400,4800",
    "worship pop 500/2000/5000, 1000/4000/10000, 1500/6000/15000",
    "LV evolve 17,33,49",
    "business LV caps 10,16,26 (26 not in file)",
    "imperial tax percents 10,19,26 (19 and 26 not in file)",
    "employment arrays (Circus Maximus 96 is not a table -- 96 only at rank[988])",
    "entertainment service radii 5,7,9 / 7,9,11",
    "goal shift -1,-1,0,+1,+1",
)


def find_seq(values: list[int], needle: list[int]) -> list[int]:
    hits = []
    n = len(needle)
    if n == 0 or n > len(values):
        return hits
    for i in range(len(values) - n + 1):
        if values[i : i + n] == needle:
            hits.append(i)
    return hits


def range_at(index: int) -> tuple[int, int, str, str, str]:
    for start, end, rid, conf, title in RANGES:
        if start <= index < end:
            return start, end, rid, conf, title
    return index, index + 1, "unmapped", "unknown", ""


def item_label(index: int, value: int) -> str:
    start, end, rid, _conf, _title = range_at(index)
    slot = index - start
    if rid == "diff_starting_money" or rid == "diff_param_a" or rid == "diff_money_b":
        return f"{DIFFICULTIES[slot]} {rid}"
    if rid == "house_occupancy":
        return f"{HOUSE_GRADES[slot]} occupancy"
    if rid == "house_tax_wealth":
        return f"{HOUSE_GRADES[slot]} tax/wealth"
    if rid == "house_lv_bonus_radius":
        grade = HOUSE_GRADES[slot // 2]
        kind = "bonus" if slot % 2 == 0 else "radius"
        return f"{grade} land {kind}"
    if rid == "forum_worship_lv":
        names = (
            ["Aventine"] * 8
            + ["Janiculan"] * 8
            + ["Palatine"] * 8
            + ["Shrine"] * 8
            + ["Temple"] * 8
            + ["Basilica"] * 8
        )
        kind = "bonus" if slot % 2 == 0 else "radius"
        return f"{names[slot]} g{slot % 8 // 2 + 1} {kind}"
    if rid == "worship_costs":
        return ("Shrine", "Temple", "Basilica")[slot]
    if rid == "entertainment_costs":
        return ("Theater", "Odeum", "Arena", "Coliseum", "Circus", "Circus Maximus")[slot]
    if rid == "province_costs":
        return (
            "Road", "Wall", "Fort", "Work camp", "Farm/Mine/Quarry",
            "Port", "Warehouse", "Shipyard", "Trading post",
        )[slot]
    if rid == "rank_individual" or rid == "rank_average":
        diff = slot // 20
        rank = slot % 20
        rname = RANKS_10[rank] if rank < 10 else f"rank{rank}"
        kind = "individual" if rid == "rank_individual" else "average"
        return f"{DIFFICULTIES[diff]} {rname} {kind}%"
    if rid == "imperial_tax_brackets":
        return ("savings>=8000 band", "savings>=5000 band", "savings>=3000 band")[slot]
    if rid == "city_build_costs":
        names = (
            "Gardens", "Plaza", "Well", "Baths", "Hospital|Rhetor", "Fountain",
            "Barracks|Janiculan", "Prefecture|Aventine", "Market", "Business",
            "Grammaticus", "Rhetor|Hospital", "Library",
        )
        return names[slot]
    if value == 99 and rid in ("rank_individual", "rank_average"):
        return f"{rid} empty"
    return rid


def coverage(n: int) -> dict[str, int]:
    counts = Counter()
    for i in range(n):
        counts[range_at(i)[3]] += 1
    return dict(counts)


def load_ints(path: Path) -> tuple[bytes, list[int]]:
    data = path.read_bytes()
    if len(data) != 4360:
        raise ValueError(f"{path.name}: size {len(data)} (expected 4360 = 1090x4)")
    values = list(struct.unpack("<1090i", data))
    return data, values


def find_bytes(hay: bytes, needle: bytes) -> list[int]:
    out = []
    start = 0
    while True:
        p = hay.find(needle, start)
        if p < 0:
            return out
        out.append(p)
        start = p + 1


def scan_exe(exe_path: Path, values: list[int]) -> None:
    exe = exe_path.read_bytes()
    print(f"=== PS.EXE light scan ({len(exe)} bytes) ===")
    print("  C2MODEL.DAT as a blob: "
          f"{'YES' if exe.find(struct.pack('<1090i', *values)) >= 0 else 'NO'}")
    for s in (b"C2MODEL.DAT", b"c2model.dat", b"C2MODEL", b"c2model"):
        print(f"  {s!r}: {find_bytes(exe, s)[:4] or '(none)'}")
    for name, seq in (
        ("starting_money[5:10]", values[5:10]),
        ("occupancy[215:247]", values[215:247]),
        ("worship[115:118]", values[115:118]),
        ("entertainment[118:124]", values[118:124]),
        ("province[197:206]", values[197:206]),
        ("tax_brackets[1020:1023]", values[1020:1023]),
        ("front[0:15]", values[0:15]),
        ("city_costs[102:124]", values[102:124]),
        ("ranks_novice_ind[790:795]", values[790:795]),
    ):
        packed = struct.pack(f"<{len(seq)}i", *seq)
        hits = find_bytes(exe, packed)
        print(f"  {name:28s} {len(hits)} hit(s) file-off {hits[:4]}")
    print("  note: tables exist as scattered .data near EOF, not one 4360-byte embed.")
    print("  filename C2MODEL.DAT is not an ASCII string (history.dat / regions.dat are).")


def emit_json(path: Path, values: list[int]) -> None:
    rows = []
    for i, v in enumerate(values):
        start, end, rid, conf, title = range_at(i)
        rows.append({
            "index": i,
            "value": v,
            "range": [start, end],
            "id": rid,
            "confidence": conf,
            "label": item_label(i, v),
        })
    cov = coverage(len(values))
    named = cov.get("high", 0) + cov.get("medium", 0)
    payload = {
        "file": "C2MODEL.DAT",
        "bytes": 4360,
        "count": len(values),
        "endian": "little",
        "record_structure": "heterogeneous tables + zero pads; not one stride",
        "coverage": cov,
        "named_high_medium": named,
        "named_pct": round(100.0 * named / len(values), 1),
        "ranges": [
            {
                "start": a,
                "end": b,
                "id": rid,
                "confidence": conf,
                "title": title,
            }
            for a, b, rid, conf, title in RANGES
        ],
        "values": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote         : {path}  ({path.stat().st_size} bytes)")


def emit_md_table(path: Path, values: list[int]) -> None:
    cov = coverage(len(values))
    named = cov.get("high", 0) + cov.get("medium", 0)
    lines = [
        "# C2MODEL.DAT labeled dump (generated)",
        "",
        f"1090 int32 LE. Named high+medium: **{named}/1090 ({100*named/1090:.1f}%)**.",
        "",
        "| Start | End | N | Conf | Id | Meaning |",
        "|---:|---:|---:|---|---|---|",
    ]
    for start, end, rid, conf, title in RANGES:
        short = title.replace("|", "/").split(".")[0]
        lines.append(
            f"| {start} | {end} | {end-start} | {conf} | `{rid}` | {short} |"
        )
    lines += ["", "## Values", "", "| Index | Value | Id | Label | Conf |",
              "|---:|---:|---|---|---|"]
    for i, v in enumerate(values):
        _a, _b, rid, conf, _t = range_at(i)
        lines.append(f"| {i} | {v} | `{rid}` | {item_label(i, v)} | {conf} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote         : {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump C2MODEL.DAT int32 tables.")
    parser.add_argument("--dat", type=Path, default=DEFAULT_GAME / "C2MODEL.DAT")
    parser.add_argument("--width", type=int, default=10, help="ints per dump row")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write index\\tvalue TSV (numbers only)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="write labeled JSON (ok to commit; no binary)",
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=None,
        help="write generated range+value markdown table",
    )
    parser.add_argument(
        "--exe",
        type=Path,
        default=None,
        help="light-scan PS.EXE for the same int32 runs (file offsets)",
    )
    args = parser.parse_args(argv)

    data, values = load_ints(args.dat)
    n = len(values)
    cov = coverage(n)
    named = cov.get("high", 0) + cov.get("medium", 0)

    print("=== C2MODEL.DAT ===")
    print(f"file          : {args.dat}  ({len(data)} bytes, {n} int32 LE)")
    print(f"min/max       : {min(values)} / {max(values)}")
    print(f"zeros         : {values.count(0)}")
    print(f"negatives     : {sum(1 for v in values if v < 0)}")
    uniq = Counter(values)
    print(f"unique values : {len(uniq)}")
    print("most common   : " + ", ".join(f"{v}*{c}" for v, c in uniq.most_common(12)))
    print(
        f"coverage      : high={cov.get('high',0)} medium={cov.get('medium',0)} "
        f"low={cov.get('low',0)} pad={cov.get('pad',0)} "
        f"unknown={cov.get('unknown',0)}"
    )
    print(
        f"named         : {named}/{n} ({100.0*named/n:.1f}%)  "
        f"[high+medium; pad is known-empty, not named]"
    )

    print("-- record structure --")
    print("  whole-file strides that divide 1090: 2,5,10,109,218,545")
    print("  conclusion: NOT a uniform record array. Mixed tables + zero pads.")
    print("  sub-records: 5-wide difficulty; 32-wide housing; 20-wide ranks;")
    print("               2-wide (land bonus,radius); 4-wide difficulty rows.")

    print("-- FAQ / known sequences --")
    for name, seq in FAQ_SEQ.items():
        hits = find_seq(values, seq)
        if hits:
            print(f"  HIT  {name:28s}  at index {hits}  (len {len(seq)})")
            continue
        if name == "house_land_value_required":
            print(f"  MISS {name:28s}  false-partial at [214] (pad 0 + occupancy)")
            continue
        print(f"  miss {name}")
    print("-- FAQ / mechanics ABSENT from this file --")
    for line in ABSENT_FAQ:
        print(f"  - {line}")

    print("-- labeled ranges --")
    for start, end, rid, conf, title in RANGES:
        preview = " ".join(str(v) for v in values[start:min(end, start + 8)])
        if end - start > 8:
            preview += " ..."
        print(f"  [{start:4d}:{end:4d}] {conf:7s} {rid:28s} {preview}")

    print("-- dump --")
    w = max(1, args.width)
    for row in range(0, n, w):
        chunk = values[row : row + w]
        body = " ".join(f"{v:7d}" for v in chunk)
        rid = range_at(row)[2]
        print(f"  [{row:4d}] {body}  # {rid}")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write("index\tvalue\tid\tconfidence\tlabel\n")
            for i, v in enumerate(values):
                _a, _b, rid, conf, _t = range_at(i)
                fh.write(f"{i}\t{v}\t{rid}\t{conf}\t{item_label(i, v)}\n")
        print(f"wrote         : {args.out}")

    if args.json is not None:
        emit_json(args.json, values)
    if args.md is not None:
        emit_md_table(args.md, values)
    if args.exe is not None:
        scan_exe(args.exe, values)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        sys.exit(1)
