"""Step 0: check that the local MMASH files are the ones this analysis used.

PhysioNet's SHA256SUMS.txt covers MMASH.zip, which is unpacked during
download, so instead each extracted CSV is compared with the committed
manifest docs/data_manifest.sha256.

    python python/00_check_data.py          # verify (exit code 1 on mismatch)
    python python/00_check_data.py --write  # regenerate the manifest
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0" / "MMASH" / "DataPaper"
MANIFEST = ROOT / "docs" / "data_manifest.sha256"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current() -> dict[str, str]:
    return {p.relative_to(RAW).as_posix(): sha256(p) for p in sorted(RAW.rglob("*.csv"))}


def main() -> None:
    if not RAW.is_dir():
        sys.exit(f"Data folder not found: {RAW}\nSee README, section 'Reproduction'.")
    files = current()
    if "--write" in sys.argv:
        MANIFEST.write_text("".join(f"{h}  {f}\n" for f, h in files.items()), encoding="utf-8")
        print(f"Wrote {len(files)} checksums to {MANIFEST.relative_to(ROOT)}")
        return
    expected = dict(line.split("  ")[::-1] for line in MANIFEST.read_text(encoding="utf-8").splitlines())
    missing = sorted(set(expected) - set(files))
    changed = sorted(f for f in expected if f in files and files[f] != expected[f])
    for f in missing:
        print("MISSING ", f)
    for f in changed:
        print("CHANGED ", f)
    if missing or changed:
        sys.exit(1)
    print(f"OK: all {len(expected)} MMASH CSV files match the manifest.")


if __name__ == "__main__":
    main()
