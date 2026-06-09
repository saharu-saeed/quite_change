# -*- coding: utf-8 -*-
"""Promote a staging result (from research/serve.py) into a canonical sector JSON file.

Staging entries live in `research/staging/{code}.json` and are written automatically
by the interactive web UI. They are NEVER auto-merged into `data/` — you decide
which entries are good enough to promote, and which to delete.

Common workflows:

  # List everything in staging:
  python -m research.promote_staging

  # Inspect a single staging entry:
  python -m research.promote_staging --show 7974

  # Promote into a non-IT sector file:
  python -m research.promote_staging --promote 1332 --to-sector AgriFishery

  # Force-overwrite if the code already exists in the target sector:
  python -m research.promote_staging --promote 1332 --to-sector AgriFishery --force

  # Delete a staging entry without promoting it:
  python -m research.promote_staging --delete 7974

  # Delete ALL staging entries (after you've promoted what you want):
  python -m research.promote_staging --clear-all --yes

Notes on IT:
  The IT sector uses a Python module (build/build_view.py) to load its data,
  not a single JSON file. Promoting to IT writes a small JSON file under
  data/it_staged_additions/{code}.json instead — the build script picks
  these up on the next build. They never modify build_view.py's source data."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent
STAGING_DIR = HERE / "staging"
DATA_DIR = PROJECT_ROOT / "data"
IT_STAGED_ADDITIONS_DIR = DATA_DIR / "it_staged_additions"

# Map sector key → canonical sector JSON file under data/
SECTOR_FILES = {
    "LandTransport": "company_research_land_transport_sector.json",
    "Mining":        "company_research_mining_sector.json",
    "Petroleum":     "company_research_petroleum_sector.json",
    "Marine":        "company_research_marine_sector.json",
    "AirTransport":  "company_research_air_transport_sector.json",
    "AgriFishery":   "company_research_agri_fishery_sector.json",
    # IT is handled separately — see _promote_to_it().
}


def _load_staging(code: str) -> dict:
    p = STAGING_DIR / f"{code}.json"
    if not p.exists():
        raise FileNotFoundError(f"No staging entry for {code} at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _strip_meta(entry: dict) -> dict:
    """Drop the staging-specific _meta and _staging_path before promoting."""
    out = dict(entry)
    out.pop("_meta", None)
    out.pop("_staging_path", None)
    return out


def cmd_list() -> int:
    if not STAGING_DIR.exists() or not any(STAGING_DIR.glob("*.json")):
        print("(staging is empty — nothing to promote)", file=sys.stderr)
        return 0
    print(f"Staging entries in {STAGING_DIR}:")
    print(f"  {'code':<6} {'tab':<7} {'bucket':<32} {'saved_at':<22} input_name")
    for p in sorted(STAGING_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            meta = data.get("_meta", {})
            tab = data.get("tab", "?")
            bucket = data.get("bucket", "")
            saved = meta.get("saved_at", "")
            name = meta.get("input_name", "")
            print(f"  {p.stem:<6} {tab:<7} {bucket:<32} {saved:<22} {name}")
        except Exception as e:  # noqa: BLE001
            print(f"  {p.stem}  (unreadable: {e})")
    return 0


def cmd_show(code: str) -> int:
    try:
        data = _load_staging(code)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_delete(code: str) -> int:
    p = STAGING_DIR / f"{code}.json"
    if not p.exists():
        print(f"ERROR: no staging entry for {code}", file=sys.stderr)
        return 1
    p.unlink()
    print(f"Deleted {p}", file=sys.stderr)
    return 0


def cmd_clear_all(confirmed: bool) -> int:
    if not confirmed:
        print("Refusing to clear staging without --yes flag.", file=sys.stderr)
        return 1
    n = 0
    if STAGING_DIR.exists():
        for p in STAGING_DIR.glob("*.json"):
            p.unlink()
            n += 1
    print(f"Deleted {n} staging entries.", file=sys.stderr)
    return 0


def _promote_to_sector_file(code: str, sector: str, force: bool) -> int:
    """Append a staging entry into data/company_research_<sector>_sector.json."""
    fname = SECTOR_FILES[sector]
    sector_path = DATA_DIR / fname
    if not sector_path.exists():
        print(f"ERROR: target sector file does not exist: {sector_path}", file=sys.stderr)
        return 1

    sector_data = json.loads(sector_path.read_text(encoding="utf-8"))
    if not isinstance(sector_data, dict):
        print(f"ERROR: target file has unexpected shape (expected dict): {sector_path}", file=sys.stderr)
        return 1

    if code in sector_data and not force:
        print(
            f"ERROR: {code} already exists in {fname}.\n"
            f"       Re-run with --force to overwrite. Current entry:\n"
            f"       name = {sector_data[code].get('name', '?')}",
            file=sys.stderr,
        )
        return 2

    try:
        entry = _load_staging(code)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    stripped = _strip_meta(entry)
    sector_data[code] = stripped

    sector_path.write_text(json.dumps(sector_data, ensure_ascii=False, indent=2), encoding="utf-8")
    action = "OVERWROTE" if force and code in sector_data else "Added"
    print(f"{action} {code} ({stripped.get('name', '?')}) into {fname}", file=sys.stderr)
    return 0


def _promote_to_it(code: str, force: bool) -> int:
    """Write the entry to data/it_staged_additions/{code}.json.

    The IT sector loads its data via build/build_view.py (a Python module),
    not a single JSON file. Rather than modify the module's source data, we
    drop the entry into a parallel directory that the build script can pick
    up. The senior reviews these before they get rolled into the canonical
    data manually.
    """
    IT_STAGED_ADDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    target = IT_STAGED_ADDITIONS_DIR / f"{code}.json"
    if target.exists() and not force:
        print(
            f"ERROR: {target} already exists. Re-run with --force to overwrite.",
            file=sys.stderr,
        )
        return 2
    try:
        entry = _load_staging(code)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    target.write_text(json.dumps(_strip_meta(entry), ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {target.relative_to(PROJECT_ROOT)}.\n"
        "Note: IT staged additions are stored separately from the main IT module.\n"
        "      They need to be manually folded into build/build_view.py for the\n"
        "      dashboard to pick them up.",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote, inspect, or delete staging entries from research/serve.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Common workflows:", 1)[-1] if __doc__ else "",
    )
    parser.add_argument("--show", metavar="CODE",
                        help="Print the full JSON for one staging entry.")
    parser.add_argument("--promote", metavar="CODE",
                        help="Promote one staging entry into a sector file. Requires --to-sector.")
    parser.add_argument("--to-sector", choices=list(SECTOR_FILES) + ["IT"],
                        help="Target sector for --promote.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing entry in the target sector.")
    parser.add_argument("--delete", metavar="CODE",
                        help="Delete one staging entry (does NOT touch data/).")
    parser.add_argument("--clear-all", action="store_true",
                        help="Delete ALL staging entries.")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm --clear-all without prompt.")
    args = parser.parse_args()

    if args.show:
        return cmd_show(args.show)
    if args.delete:
        return cmd_delete(args.delete)
    if args.clear_all:
        return cmd_clear_all(args.yes)
    if args.promote:
        if not args.to_sector:
            print("ERROR: --promote requires --to-sector.", file=sys.stderr)
            return 1
        if args.to_sector == "IT":
            return _promote_to_it(args.promote, args.force)
        return _promote_to_sector_file(args.promote, args.to_sector, args.force)

    # No action flags → list mode
    return cmd_list()


if __name__ == "__main__":
    sys.exit(main())
