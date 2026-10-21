# Validation and reproducibility

## Input data

`python/00_check_data.py` compares the SHA-256 checksum of each extracted MMASH CSV file (153 files) with `docs/data_manifest.sha256`. `run_all.sh` stops if any file is missing or different.

PhysioNet's own `SHA256SUMS.txt` covers `MMASH.zip` rather than the individual CSV files. On 21 October 2026, the manifest was therefore linked to the official release:

1. the PhysioNet download (`multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0.zip`) was unpacked into an empty folder;
2. its `MMASH.zip` (SHA-256 `ef91ee1b…f70726`) and `LICENSE.txt` (`bcdfcd4f…d12017`) matched PhysioNet's `SHA256SUMS.txt`;
3. `MMASH.zip` was unpacked into another empty folder; its 153 CSV files matched `docs/data_manifest.sha256` exactly (none missing, none extra, none different).

So a data folder that passes `00_check_data.py` contains exactly the CSV files of the official MMASH v1.0.0 release.

## Checks made during the analysis

| Check | Finding | Action |
|---|---|---|
| Day coding in `RR.csv` | Users 8 and 9 code day 2 as `-29`; in time order those rows follow day 1 | Recoded to 2; the script also stops if timestamps are not in order |
| Artefact rates | User 4: 22 % of beats removed. Inspection showed IBIs of ~1.6–1.7 s alternating with ~0.8 s, i.e. missed R-peaks | Kept, rejected beats removed; user 4 has only 22 % usable windows |
| Window coverage | With an initial 80 % threshold only 10 of 6,154 windows qualified. All recordings miss ~8 s of beats about every 33 s, so coverage never exceeds ~78 % | Threshold set to 60 % (≥ 180 s); successive differences across gaps > 3 s excluded |
| Sleep dates | Users 3, 5, 13 and 19 have get-up dated day 1 after a pre-midnight bedtime | Get-up moved to the next day when it precedes bedtime |
| Two sleep periods | User 1's awakening between periods would have been labelled wake | Whole night (first bedtime to last get-up) treated as not-wake |
| MEQ interaction | Random-intercept model gave p ≈ 3 × 10⁻⁵. MEQ is between-person, so individual curve-shape differences were absorbed by MEQ | Participant-specific smooths added; effect shrank (edf 6.8 → 3.4) and is not interpreted |
| Missing PANAS | User 13 lacks the 14:00 rating, which made all of user 13's person-centred values missing in the plot | Missing ratings dropped before centring |
| Plausibility | Median RMSSD 34 ms and mean HR 75 bpm in usable windows; HR lower and RMSSD higher in sleep | Consistent with values for healthy young adults |
| Reference list | Every reference was checked against PhysioNet or Crossref. Balter et al. (2024) use GAMMs for self-reported symptoms, not HRV | Cited only as the source of the model family |

## Fresh-run comparison

On 17 October 2026, the committed repository was cloned into an empty folder. The MMASH data were copied in, and `./run_all.sh` was run on Windows 11 with Python 3.13.15 (pandas 3.0.5, numpy 2.5.3), R 4.6.1 (tidyverse 2.0.0, mgcv 1.9.4) and Quarto 1.10.18. It finished without errors in about 50 s.

Compared with the committed versions:

- all tables in `output/tables/` and figures in `output/figures/` were identical, apart from line endings, which Git normalises;
- `report/report.html` was identical;
- `report/report.pdf` differed only in its embedded creation date.

To repeat the check, run the pipeline and then `git status`. Only `report/report.pdf` and, if run on a different day, `report/report.html` should show as changed, because both carry the render date (`date: today`); the PDF's creation timestamp is recorded in UTC. If other outputs differ, investigate the cause (for example different package versions or a different data download) rather than editing expected values.

Python package versions are pinned in `requirements.txt`. R package versions are not pinned, and a different mgcv version can change GAMM estimates slightly; the full R session (`sessionInfo()`, all package versions) is recorded in `docs/R_session_info.txt`. If results differ, install those versions before investigating further.
