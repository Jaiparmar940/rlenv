#!/usr/bin/env python3
"""Stage the environment source into each deployment directory's ``vendor/``.

``hud deploy`` tarballs the environment directory and nothing above it, so a
deployable directory has to be self-contained. Rather than fork the domain
code, this script mirrors the *authoritative* package into ``vendor/`` right
before a build. ``vendor/`` is gitignored: the repository keeps exactly one
copy of every environment, and ``--check`` (also asserted by the parity tests)
proves the staged tree is byte-identical to its source.

    python deploy/hud/stage.py            # stage both environments
    python deploy/hud/stage.py --check    # verify staged == source, stage nothing
    python deploy/hud/stage.py --clean    # remove vendor/ trees

Nothing here is required for local iteration: ``adapter_core`` falls back to the
checkout's own source tree when ``vendor/`` is absent.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

HUD_DIR = Path(__file__).resolve().parent
REPO = HUD_DIR.parent.parent

# (deployment directory, source package, package name inside vendor/)
PACKAGES: list[tuple[str, Path, str]] = [
    ("no-start-env", REPO / "src" / "nostart", "nostart"),
    (
        "decision-layer-kitchen",
        REPO / "decision-layer" / "kitchen_task",
        "kitchen_task",
    ),
]

# Caches only. The mirror is otherwise exact, so provenance is a byte compare.
# (kitchen_task/backends/robocasa_backend.py ships but is never imported by the
# managed environment — it needs the sim extras; see that env's README.)
SKIP = {"__pycache__", ".DS_Store", ".pytest_cache"}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store")


def _vendor_dir(env_dir: str) -> Path:
    return HUD_DIR / env_dir / "vendor"


def stage() -> int:
    for env_dir, source, package in PACKAGES:
        if not source.is_dir():
            print(f"[stage] MISSING SOURCE {source}", file=sys.stderr)
            return 1
        target = _vendor_dir(env_dir) / package
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, ignore=IGNORE)
        count = sum(1 for _ in target.rglob("*.py"))
        print(
            f"[stage] {source.relative_to(REPO)} -> "
            f"{target.relative_to(REPO)} ({count} modules)"
        )
    return 0


def drift(source: Path, target: Path) -> list[str]:
    """Relative paths that differ between a source package and its mirror."""
    if not target.is_dir():
        return ["<not staged>"]
    return _walk(filecmp.dircmp(source, target, ignore=sorted(SKIP)), Path())


def _walk(cmp: filecmp.dircmp, prefix: Path) -> list[str]:
    out = [str(prefix / name) for name in cmp.diff_files]
    out += [str(prefix / name) for name in cmp.left_only if name not in SKIP]
    out += [str(prefix / name) for name in cmp.right_only if name not in SKIP]
    out += [str(prefix / name) for name in cmp.funny_files]
    for name, sub in cmp.subdirs.items():
        if name in SKIP:
            continue
        out += _walk(sub, prefix / name)
    return sorted(out)


def check() -> int:
    failures = 0
    for env_dir, source, package in PACKAGES:
        target = _vendor_dir(env_dir) / package
        bad = drift(source, target)
        if bad:
            print(f"[check] DRIFT {env_dir}/vendor/{package}: {bad}", file=sys.stderr)
            failures += 1
        else:
            print(f"[check] OK {env_dir}/vendor/{package}")
    return 1 if failures else 0


def clean() -> int:
    for env_dir, _, _ in PACKAGES:
        vendor = _vendor_dir(env_dir)
        if vendor.exists():
            shutil.rmtree(vendor)
            print(f"[clean] removed {vendor.relative_to(REPO)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check", action="store_true", help="verify staged trees match their sources"
    )
    group.add_argument("--clean", action="store_true", help="remove vendor/ trees")
    args = parser.parse_args()
    if args.check:
        return check()
    if args.clean:
        return clean()
    return stage()


if __name__ == "__main__":
    sys.exit(main())
