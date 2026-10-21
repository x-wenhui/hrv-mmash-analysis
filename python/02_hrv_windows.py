"""Step 2: compute time-domain HRV in consecutive 5-min windows.

Input : derived/rr_clean.csv.gz        (from 01_clean_rr.py)
Output: derived/hrv_5min.csv           one row per user x 5-min window
        output/tables/window_quality.csv     usable windows per user
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "derived"
RESULTS = ROOT / "output" / "tables"

WINDOW = "5min"
WINDOW_S = 300
# MMASH RR files have a systematic dropout pattern: roughly every 33 s about
# 8 s of beats are missing (~25 % of clock time), so a 5-min window can reach
# at most ~78 % coverage. We therefore require >= 60 % (180 s of valid NN
# intervals), which is still above the ~1-3 min shown to be sufficient for
# ultra-short RMSSD. Successive differences across these gaps are excluded
# in step 1 (MAX_GAP).
MIN_COVERAGE = 0.60     # valid IBIs must sum to >= 60 % of the window (180 s)
MAX_ARTEFACT = 0.20     # <= 20 % of beats in the window removed
MIN_PAIRS = 100         # valid successive differences needed for RMSSD


def window_metrics(g: pd.DataFrame) -> pd.Series:
    nn = g.loc[g["valid"], "ibi_s"].to_numpy() * 1000          # ms
    # successive differences only between adjacent valid beats
    ibi_ms = g["ibi_s"].to_numpy() * 1000
    pair = g["valid_pair"].to_numpy()
    sd = (ibi_ms[1:] - ibi_ms[:-1])[pair[1:]]
    n_valid = len(nn)
    rmssd = np.sqrt(np.mean(sd ** 2)) if len(sd) > 1 else np.nan
    return pd.Series({
        "n_beats": len(g),
        "n_valid": n_valid,
        "n_pairs": len(sd),
        "coverage": nn.sum() / 1000 / WINDOW_S,
        "pct_artefact": 1 - n_valid / len(g),
        "mean_hr": 60000 / nn.mean() if n_valid else np.nan,
        "sdnn": nn.std(ddof=1) if n_valid > 1 else np.nan,
        "rmssd": rmssd,
    })


def main() -> None:
    rr = pd.read_csv(DERIVED / "rr_clean.csv.gz", parse_dates=["timestamp"])
    rr["window_start"] = rr["timestamp"].dt.floor(WINDOW)   # clock-aligned windows
    hrv = (rr.groupby(["user", "window_start"])
             .apply(window_metrics, include_groups=False)
             .reset_index())
    hrv["ln_rmssd"] = np.log(hrv["rmssd"])
    hrv["clock_hour"] = hrv["window_start"].dt.hour + hrv["window_start"].dt.minute / 60
    hrv["usable"] = ((hrv["coverage"] >= MIN_COVERAGE)
                     & (hrv["pct_artefact"] <= MAX_ARTEFACT)
                     & (hrv["n_pairs"] >= MIN_PAIRS))
    hrv.round({c: 4 for c in hrv.columns if c not in ("user", "window_start", "usable")}).to_csv(DERIVED / "hrv_5min.csv", index=False)

    q = (hrv.groupby("user")
            .agg(n_windows=("usable", "size"), n_usable=("usable", "sum"))
            .assign(pct_usable=lambda d: (100 * d.n_usable / d.n_windows).round(1))
            .reset_index())
    q.to_csv(RESULTS / "window_quality.csv", index=False)
    print(q.to_string(index=False))
    u = hrv[hrv.usable]
    print(f"\nUsable windows: {len(u)} of {len(hrv)}")
    print(u[["mean_hr", "sdnn", "rmssd", "ln_rmssd"]].describe().round(2).to_string())


if __name__ == "__main__":
    main()
