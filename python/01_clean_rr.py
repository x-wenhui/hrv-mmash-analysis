"""Step 1: read Polar H7 inter-beat intervals (RR.csv), build timestamps,
flag artefacts, and report the percentage removed per participant.

Input : data/.../MMASH/DataPaper/user_*/RR.csv  (raw, not committed)
Output: derived/rr_clean.csv.gz        beat-level data with artefact flags
        output/tables/artefact_summary.csv   % of beats removed per user and rule
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0" / "MMASH" / "DataPaper"
DERIVED = ROOT / "derived"
RESULTS = ROOT / "output" / "tables"

# Artefact parameters (documented in README)
IBI_MIN, IBI_MAX = 0.3, 2.0   # s; = 200 and 30 bpm, physiological range
LOCAL_WIN = 11                # beats in the centred local-median reference
MAX_DEV = 0.20                # max relative deviation from local median (Malik-type 20 % rule)
MAX_GAP = 3.0                 # s; a larger jump in clock time = recording gap

# Arbitrary reference date: MMASH gives only "day 1 / day 2", not calendar dates.
DAY1 = pd.Timestamp("2000-01-01")


def read_rr(user_dir: Path) -> pd.DataFrame:
    rr = pd.read_csv(user_dir / "RR.csv", index_col=0)
    # Users 8 and 9 code the second day as -29 (a month-rollover bug in the
    # export); in time order those rows follow day 1, so they are day 2.
    rr["day"] = rr["day"].replace(-29, 2)
    rr["timestamp"] = (DAY1 + pd.to_timedelta(rr["day"] - 1, unit="D")
                       + pd.to_timedelta(rr["time"]))
    return rr


def flag_artefacts(rr: pd.DataFrame) -> pd.DataFrame:
    ibi = rr["ibi_s"]
    rr["bad_range"] = (ibi < IBI_MIN) | (ibi > IBI_MAX)

    # Successive-difference rule against a robust local reference: the median
    # of the surrounding in-range beats. Comparing with a local median (rather
    # than only the previous beat) avoids also rejecting the normal beat that
    # follows a single ectopic/missed beat.
    ref = ibi.where(~rr["bad_range"]).rolling(LOCAL_WIN, center=True, min_periods=5).median()
    rr["bad_diff"] = ~rr["bad_range"] & ((ibi - ref).abs() / ref > MAX_DEV)
    rr["valid"] = ~(rr["bad_range"] | rr["bad_diff"])

    # A successive difference is usable only if both beats are valid AND
    # adjacent in the original series without a recording gap in between.
    gap = rr["timestamp"].diff().dt.total_seconds() > MAX_GAP
    rr["valid_pair"] = rr["valid"] & rr["valid"].shift(fill_value=False) & ~gap
    return rr


def main() -> None:
    DERIVED.mkdir(exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    users = sorted(RAW.glob("user_*"), key=lambda p: int(p.name.split("_")[1]))
    beats, summary = [], []
    for d in users:
        rr = read_rr(d)
        if not rr["timestamp"].is_monotonic_increasing:
            raise ValueError(f"{d.name}: timestamps not in order")
        rr = flag_artefacts(rr)
        rr.insert(0, "user", int(d.name.split("_")[1]))
        beats.append(rr[["user", "timestamp", "ibi_s", "bad_range", "bad_diff", "valid", "valid_pair"]])
        n = len(rr)
        summary.append({
            "user": int(d.name.split("_")[1]),
            "n_beats": n,
            "record_hours": round((rr["timestamp"].iloc[-1] - rr["timestamp"].iloc[0]).total_seconds() / 3600, 2),
            "pct_out_of_range": round(100 * rr["bad_range"].mean(), 2),
            "pct_succ_diff": round(100 * rr["bad_diff"].mean(), 2),
            "pct_removed_total": round(100 * (~rr["valid"]).mean(), 2),
        })

    pd.concat(beats).to_csv(DERIVED / "rr_clean.csv.gz", index=False)
    summary = pd.DataFrame(summary)
    summary.to_csv(RESULTS / "artefact_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"\nMedian % removed: {summary['pct_removed_total'].median():.2f} "
          f"(range {summary['pct_removed_total'].min():.2f}-{summary['pct_removed_total'].max():.2f})")


if __name__ == "__main__":
    main()
