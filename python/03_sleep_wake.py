"""Step 3: label 5-min HRV windows as sleep / wake using the actigraphy sleep
periods (sleep.csv) and summarise sleep vs wake HRV per participant.

Input : derived/hrv_5min.csv, data/.../user_*/sleep.csv
Output: derived/hrv_5min_state.csv     windows with state label
        derived/sleep_periods.csv      cleaned sleep periods
        output/tables/sleep_wake_hrv.csv     per-user medians, sleep vs wake
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0" / "MMASH" / "DataPaper"
DERIVED = ROOT / "derived"
RESULTS = ROOT / "output" / "tables"
DAY1 = pd.Timestamp("2000-01-01")   # same arbitrary reference date as step 1
WINDOW = pd.Timedelta("5min")
METRICS = ["mean_hr", "sdnn", "rmssd", "ln_rmssd"]


def to_ts(day: pd.Series, time: pd.Series) -> pd.Series:
    return DAY1 + pd.to_timedelta(day - 1, unit="D") + pd.to_timedelta(time + ":00")


def read_sleep() -> pd.DataFrame:
    rows = []
    for d in RAW.glob("user_*"):
        s = pd.read_csv(d / "sleep.csv", index_col=0)
        if s.empty:          # user 11: no sleep data
            continue
        s["user"] = int(d.name.split("_")[1])
        rows.append(s)
    s = pd.concat(rows, ignore_index=True)
    s["in_bed"] = to_ts(s["In Bed Date"], s["In Bed Time"])
    s["onset"] = to_ts(s["Onset Date"], s["Onset Time"])
    s["out_bed"] = to_ts(s["Out Bed Date"], s["Out Bed Time"])
    # Users 3, 5, 13, 19 have the out-of-bed date coded as day 1 even though
    # they went to bed before midnight on day 1; get-up must follow bedtime.
    for col in ["onset", "out_bed"]:
        s.loc[s[col] < s["in_bed"], col] += pd.Timedelta("1D")
    return s[["user", "in_bed", "onset", "out_bed"]].sort_values(["user", "in_bed"])


def label_state(hrv: pd.DataFrame, sleep: pd.DataFrame) -> pd.Series:
    """sleep = window entirely between sleep onset and getting up;
    wake = window entirely outside any in-bed period;
    transition = overlaps an in-bed period but is not fully asleep (excluded)."""
    state = pd.Series("wake", index=hrv.index)
    state[~hrv["user"].isin(sleep["user"])] = "no_sleep_data"
    start, end = hrv["window_start"], hrv["window_start"] + WINDOW
    # Whole night span (first bedtime to last get-up): user 1 has two sleep
    # periods, and the short awakening between them is not daytime wake.
    night = sleep.groupby("user").agg(in_bed=("in_bed", "min"), out_bed=("out_bed", "max"))
    for user, n in night.iterrows():
        me = hrv["user"] == user
        state[me & (end > n.in_bed) & (start < n.out_bed)] = "transition"
    for p in sleep.itertuples():
        asleep = (hrv["user"] == p.user) & (start >= p.onset) & (end <= p.out_bed)
        state[asleep] = "sleep"
    return state


def main() -> None:
    hrv = pd.read_csv(DERIVED / "hrv_5min.csv", parse_dates=["window_start"])
    sleep = read_sleep()
    sleep.to_csv(DERIVED / "sleep_periods.csv", index=False)
    hrv["state"] = label_state(hrv, sleep)
    hrv.to_csv(DERIVED / "hrv_5min_state.csv", index=False)

    u = hrv[hrv["usable"] & hrv["state"].isin(["sleep", "wake"])]
    per_user = (u.groupby(["user", "state"])[METRICS].median()
                  .unstack("state"))
    per_user.columns = [f"{m}_{s}" for m, s in per_user.columns]
    per_user["n_sleep_windows"] = u[u.state == "sleep"].groupby("user").size()
    per_user["n_wake_windows"] = u[u.state == "wake"].groupby("user").size()
    per_user["diff_ln_rmssd"] = per_user["ln_rmssd_sleep"] - per_user["ln_rmssd_wake"]
    per_user["diff_mean_hr"] = per_user["mean_hr_sleep"] - per_user["mean_hr_wake"]
    per_user = per_user.round(3).reset_index()
    per_user.to_csv(RESULTS / "sleep_wake_hrv.csv", index=False)

    cols = ["user", "n_sleep_windows", "n_wake_windows", "mean_hr_wake", "mean_hr_sleep",
            "rmssd_wake", "rmssd_sleep", "diff_ln_rmssd"]
    print(sleep.to_string(index=False), "\n")
    print(hrv["state"].value_counts().to_string(), "\n")
    print(per_user[cols].to_string(index=False))
    d = per_user["diff_ln_rmssd"]
    print(f"\nlnRMSSD sleep - wake: median {d.median():.2f}; higher in sleep for "
          f"{(d > 0).sum()} of {d.notna().sum()} participants")
    h = per_user["diff_mean_hr"]
    print(f"HR sleep - wake: median {h.median():.1f} bpm; lower in sleep for "
          f"{(h < 0).sum()} of {h.notna().sum()} participants")


if __name__ == "__main__":
    main()
