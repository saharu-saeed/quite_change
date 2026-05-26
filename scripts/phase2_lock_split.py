"""Step 1: Lock the 50/61 design/holdout split for Phase 2.

Stratifies by (cohort × verdict class × hit/miss/abstain) to ensure both
sets have meaningful representation of every important case category.

The split is LOCKED to outputs/phase2_split.json and must not be changed
once any LLM call has been made against it.
"""
from __future__ import annotations
import json
import sys
import io
import random
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
TRAIN_TICKERS = set(JGAAP_ORIG + JGAAP_OOS)

SEED = 20260520  # deterministic split
DESIGN_SIZE = 50

# Critical cases that MUST be in the design set (so we can iterate on them)
# These are the cases that drove Phase 1's veto rule discovery, plus the
# 6 stubborn uncaught misses we want Phase 2 to address.
PINNED_TO_DESIGN = [
    # The 6 stubborn uncaught misses (Phase 1 ceiling)
    ("2317", "FY2021->FY2022"),
    ("2326", "FY2023->FY2024"),
    ("3635", "FY2022->FY2023"),
    ("3661", "FY2023->FY2024"),
    ("4686", "FY2022->FY2023"),
    ("9684", "FY2021->FY2022"),
    # The Mercari pattern (caught by Rule 5 but worth keeping in design)
    ("4385", "FY2021->FY2022"),
    # Big surge cases (caught by Rule 6)
    ("4776", "FY2022->FY2023"),
    ("3760", "FY2022->FY2023"),
    # Margin-declining (caught by Rule 8)
    # 2326 FY2023->FY2024 already pinned
    # Goodwill exposure (caught by Rule 7)
    ("4071", "FY2022->FY2023"),
]


def main():
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]

    print(f"Total predictions: {len(outcomes)}")

    # Stratify by (cohort, verdict, score)
    strata = defaultdict(list)
    pinned_keys = set(PINNED_TO_DESIGN)
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        cohort = "TRAIN" if r["ticker"] in TRAIN_TICKERS else "TEST"
        bucket = (cohort, r["llm_verdict"], r["llm_lenient_score"])
        is_pinned = key in pinned_keys
        strata[bucket].append({**r, "_key": key, "_pinned": is_pinned})

    print(f"\nStrata breakdown:")
    for bucket, items in sorted(strata.items()):
        pinned_n = sum(1 for x in items if x["_pinned"])
        print(f"  {bucket}: {len(items)} cases ({pinned_n} pinned)")

    # Assignment: all pinned → design. Then fill design to 50 with
    # proportional sampling from each stratum.
    rng = random.Random(SEED)
    design = []
    holdout = []

    for bucket, items in strata.items():
        pinned = [x for x in items if x["_pinned"]]
        unpinned = [x for x in items if not x["_pinned"]]
        rng.shuffle(unpinned)
        design.extend(pinned)
        # We'll fill the rest after we know how many slots are left.
        for x in unpinned:
            x["_bucket"] = bucket
            holdout.append(x)  # tentatively in holdout, then promote some

    slots_remaining = DESIGN_SIZE - len(design)
    print(f"\nDesign-pinned: {len(design)}. Slots remaining: {slots_remaining}")

    # Proportional fill: count how many unpinned each stratum has;
    # allocate slots in proportion.
    unpinned_by_bucket = defaultdict(list)
    for x in holdout:
        unpinned_by_bucket[x["_bucket"]].append(x)
    total_unpinned = sum(len(v) for v in unpinned_by_bucket.values())
    promoted = []
    for bucket, items in unpinned_by_bucket.items():
        # Proportional share, rounded
        share = round(slots_remaining * len(items) / total_unpinned)
        promoted.extend(items[:share])

    # Trim/extend to exactly slots_remaining
    while len(promoted) > slots_remaining:
        promoted.pop()
    while len(promoted) < slots_remaining:
        # Pick from largest unused bucket
        used_keys = {p["_key"] for p in promoted}
        unused = [x for x in holdout if x["_key"] not in used_keys]
        if not unused: break
        promoted.append(unused[0])

    design.extend(promoted)
    promoted_keys = {p["_key"] for p in promoted}
    holdout = [x for x in holdout if x["_key"] not in promoted_keys]

    print(f"\nFinal: design={len(design)}  holdout={len(holdout)}  total={len(design)+len(holdout)}")

    # Verify stratification
    print(f"\nDesign-set composition:")
    d_strata = defaultdict(int)
    for x in design:
        cohort = "TRAIN" if x["ticker"] in TRAIN_TICKERS else "TEST"
        d_strata[(cohort, x["llm_verdict"], x["llm_lenient_score"])] += 1
    for k, v in sorted(d_strata.items()):
        print(f"  {k}: {v}")

    print(f"\nHoldout composition:")
    h_strata = defaultdict(int)
    for x in holdout:
        cohort = "TRAIN" if x["ticker"] in TRAIN_TICKERS else "TEST"
        h_strata[(cohort, x["llm_verdict"], x["llm_lenient_score"])] += 1
    for k, v in sorted(h_strata.items()):
        print(f"  {k}: {v}")

    # Sanity check: pinned cases all landed in design
    design_keys = {x["_key"] for x in design}
    missing_pinned = [p for p in PINNED_TO_DESIGN if p not in design_keys]
    if missing_pinned:
        print(f"\n⚠️  Pinned cases NOT in design: {missing_pinned}")
    else:
        print(f"\n✓ All {len(PINNED_TO_DESIGN)} pinned cases are in design set")

    # Save
    out = ROOT / "outputs" / "phase2_split.json"
    out.write_text(json.dumps({
        "seed": SEED,
        "design_size": len(design),
        "holdout_size": len(holdout),
        "pinned_to_design": PINNED_TO_DESIGN,
        "design": [{"ticker": x["ticker"], "prediction_pair": x["prediction_pair"]} for x in design],
        "holdout": [{"ticker": x["ticker"], "prediction_pair": x["prediction_pair"]} for x in holdout],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[LOCKED] {out}")
    print(f"   This split must not be changed once Phase 2 LLM calls are made.")


if __name__ == "__main__":
    main()
