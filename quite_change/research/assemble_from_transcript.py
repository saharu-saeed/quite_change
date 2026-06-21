# -*- coding: utf-8 -*-
"""Assemble a companies JSON from a workflow run's transcript — the ROBUST save path.

Every workflow agent persists its StructuredOutput to its own agent-*.jsonl the instant it
completes. So even if the final write-agent fails (session limit, truncation), all completed
companies are on disk. This reconstructs the merged JSON from those transcripts.

Usage:
    python -m research.assemble_from_transcript <run_dir> <out.json>
    python -m research.assemble_from_transcript <run_dir> <out.json> --prefer-deep

--prefer-deep: when a ticker has both a light and a deep (grounded) output, keep the deep one.
"""
from __future__ import annotations
import argparse, json, glob, os, sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try: _s.reconfigure(encoding="utf-8")
        except Exception: pass


def _find_structured_outputs(obj, out):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name") == "StructuredOutput":
            inp = obj.get("input")
            if isinstance(inp, dict):
                out.append(inp)
        for v in obj.values():
            _find_structured_outputs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _find_structured_outputs(v, out)


def _is_deep(rec: dict) -> bool:
    # deep/grounded outputs carry these fields; light/draft ones don't
    return "grounding_check" in rec or "corrections_made" in rec or "one_off_probe_result" in rec


def assemble(run_dir: str, prefer_deep: bool = True) -> dict:
    companies: dict[str, dict] = {}
    for f in glob.glob(os.path.join(run_dir, "agent-*.jsonl")):
        found: list[dict] = []
        try:
            for line in open(f, encoding="utf-8"):
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                _find_structured_outputs(ev, found)
        except Exception:
            continue
        for rec in found:
            t = rec.get("ticker")
            if not t:
                continue
            prev = companies.get(t)
            if prev is None:
                companies[t] = rec
            elif prefer_deep and _is_deep(rec) and not _is_deep(prev):
                companies[t] = rec          # upgrade light -> deep
            elif prefer_deep and _is_deep(rec) == _is_deep(prev):
                companies[t] = rec          # same tier -> keep latest seen
            elif not prefer_deep:
                companies[t] = rec
    return companies


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("out_path")
    ap.add_argument("--prefer-deep", action="store_true", default=True)
    ap.add_argument("--no-prefer-deep", dest="prefer_deep", action="store_false")
    args = ap.parse_args()

    if not os.path.isdir(args.run_dir):
        print(f"Error: run_dir not found: {args.run_dir}", file=sys.stderr)
        return 1

    companies = assemble(args.run_dir, prefer_deep=args.prefer_deep)
    out = {"assembled_from": args.run_dir, "count": len(companies), "companies": companies}
    os.makedirs(os.path.dirname(os.path.abspath(args.out_path)), exist_ok=True)
    with open(args.out_path, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    deep = sum(1 for c in companies.values() if _is_deep(c))
    print(f"Assembled {len(companies)} companies ({deep} deep, {len(companies)-deep} light) -> {args.out_path}",
          file=sys.stderr)
    print(",".join(sorted(companies)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
