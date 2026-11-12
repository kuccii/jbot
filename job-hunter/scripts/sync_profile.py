#!/usr/bin/env python3
"""Regenerate the ``profile:`` block of config.production.yaml from career-ops.

    python scripts/sync_profile.py                 # uses ../career-ops (sibling of the repo root)
    python scripts/sync_profile.py --career-ops /path/to/career-ops
    python scripts/sync_profile.py --check          # exit 1 if the file would change

Run from the ``job-hunter/`` directory. The VPS clone has no career-ops, so
this runs locally and the output is committed.
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_hunter import profile_sync  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]          # .../JBot
CONFIG = Path(__file__).resolve().parents[1] / "config.production.yaml"

def _default_career_ops() -> Path:
    env = os.environ.get("CAREER_OPS_DIR")
    if env:
        return Path(env)
    for cand in (
        REPO_ROOT.parent / "Automation" / "career-ops",
        REPO_ROOT.parent / "career-ops",
        REPO_ROOT / "career-ops",
    ):
        if (cand / "config" / "profile.yml").exists():
            return cand
    return REPO_ROOT.parent / "career-ops"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--career-ops", default=str(_default_career_ops()))
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--check", action="store_true", help="exit 1 if a change is needed")
    args = ap.parse_args()

    co = Path(args.career_ops)
    profile_yml = yaml.safe_load((co / "config" / "profile.yml").read_text(encoding="utf-8"))
    cv_text = (co / "cv.md").read_text(encoding="utf-8")
    profile = profile_sync.build_profile(profile_yml, cv_text)

    cfg_path = Path(args.config)
    old = cfg_path.read_text(encoding="utf-8")
    new = profile_sync.replace_profile_block(old, profile)
    if args.check:
        if old != new:
            print("profile block is stale; run scripts/sync_profile.py", file=sys.stderr)
            return 1
        print("profile block up to date")
        return 0
    cfg_path.write_text(new, encoding="utf-8")
    print(f"wrote profile block to {cfg_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
