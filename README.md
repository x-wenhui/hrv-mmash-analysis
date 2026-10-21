# Heart rate variability across 24 hours in healthy young adults

**[Report (PDF)](report/report.pdf)** · **[Report (HTML)](report/report.html)** · **[Figures](output/figures/)** · **[Validation and reproducibility](docs/VALIDATION_AND_REPRODUCIBILITY.md)**

**Research question.** How does heart rate variability (HRV) change over 24 hours of everyday life? How different is it during sleep and wakefulness? Does it relate to chronotype or to momentary affect?

This is an **independent analysis of a public dataset**. I did not collect the data. All analyses are **exploratory and non-causal**.

## Data

[MMASH v1.0.0](https://doi.org/10.13026/cerq-fc86) (Multilevel Monitoring of Activity and Sleep in Healthy People; Rossi et al., 2020, *Data* 5(4), 91, [doi:10.3390/data5040091](https://doi.org/10.3390/data5040091)) covers 22 healthy young adult men over about 24 h each. For each participant it provides:

- beat-to-beat intervals from a Polar H7 chest strap;
- actigraphy-estimated sleep periods;
- chronotype (Morningness–Eveningness Questionnaire, MEQ);
- positive and negative affect (PANAS), rated at 10:00, 14:00, 18:00 and 22:00, and at 09:00 the next day.

The data are released under the Open Database License (ODbL v1.0) and are **not redistributed** in this repository.

Data issues found and handled in the code:

| Issue | Handling |
|---|---|
| Users 8 and 9 code the second day as `-29` | Recoded to day 2 (`01_clean_rr.py`) |
| Users 3, 5, 13 and 19 have get-up dated day 1 after a pre-midnight bedtime | Get-up moved to the next day (`03_sleep_wake.py`) |
| User 1 has two sleep periods | The awakening between them is excluded, not counted as wake |
| User 11 has no sleep data; user 13 lacks one PANAS rating | Excluded from the analyses that need them |
| In every recording, about 8 s of beats are missing roughly every 33 s | Coverage threshold set to 60 %; successive differences across gaps are not used |

## Method

1. **Artefact handling (Python).** Inter-beat intervals outside 0.3–2.0 s are removed. Each remaining beat is compared with the median of the 11 surrounding in-range beats and removed if it deviates by more than 20 % (a local-median variant of the Malik 20 % rule). Successive differences are used only between two valid beats that are adjacent in the original series, with no gap > 3 s between them. The percentage removed is reported per participant.
2. **5-min windows.** Clock-aligned windows give mean HR, SDNN, RMSSD and lnRMSSD. A window is *usable* if valid intervals cover ≥ 60 % of it, ≤ 20 % of its beats were removed, and it has ≥ 100 valid successive differences.
3. **Sleep vs wake.** Windows are labelled from the actigraphy sleep periods. Per-participant medians are compared with paired Wilcoxon tests.
4. **24-h profile (R, mgcv).** A GAMM with a cyclic smooth of clock time, a participant random intercept and AR(1) errors. A sensitivity model allows participant-specific curves. An exploratory model adds a clock × MEQ interaction. This is the model family that Balter et al. (2024, *Transl Psychiatry* 14, 237, [doi:10.1038/s41398-024-02943-7](https://doi.org/10.1038/s41398-024-02943-7)) used for diurnal variation in self-reported psychiatric symptoms by chronotype; they did not study HRV.
5. **HRV and affect.** lnRMSSD in the hour before each PANAS rating, split into within- and between-person parts, enters a mixed model with time point as a covariate.

## Main findings

| Analysis | Result |
|---|---|
| Artefacts | Median 1.9 % of beats removed (0.2–22 %; user 4 has many missed beats) |
| Usable windows | 5,632 of 6,154 (92 %) |
| Sleep vs wake | lnRMSSD higher in sleep for 20 of 21 participants (median +0.41 ln ms); HR lower for 21 of 21 (median −22 bpm); both Wilcoxon p < 0.001 |
| 24-h profile | lnRMSSD rises through the night, peaks in the early morning, drops steeply around getting up, and stays low through the day; HR shows the mirror image |
| Chronotype (MEQ) | Nominal clock × MEQ interaction, but the predicted curves overlap almost entirely and the test is sensitive to the random-effect structure; **not interpreted** |
| HRV and affect | No within-person association with positive (p = 0.39) or negative (p = 0.93) affect; low power, inconclusive |

## Repository structure

```
python/   00_check_data.py   verify the local data against the checksum manifest
          01_clean_rr.py     timestamps, artefact flags, % removed per user
          02_hrv_windows.py  5-min HRV metrics and quality flags
          03_sleep_wake.py   sleep / wake labels and per-user comparison
R/        04_gamm.R          24-h GAMMs and MEQ interaction, figures
          05_panas.R         HRV before PANAS ratings
report/   report.qmd         Quarto source; report.html and report.pdf rendered
output/   tables/            summary tables and model output
          figures/           figures used in the report
docs/     VALIDATION_AND_REPRODUCIBILITY.md, data_manifest.sha256, R_session_info.txt
run_all.sh                   runs every step in order
```

`data/` (raw MMASH files) and `derived/` (intermediate beat- and window-level data) are created locally and are not committed.

## Reproduction

Tools used for the final run: Python 3.13, R 4.6 (tidyverse 2.0.0, mgcv 1.9.4, here 1.0.2, knitr 1.51, rmarkdown 2.31) and Quarto 1.10. Python package versions are pinned in `requirements.txt`. R package versions are not pinned, but the exact versions of every attached and loaded package are recorded in `docs/R_session_info.txt`.

1. Download the MMASH ZIP from PhysioNet (<https://physionet.org/content/mmash/get-zip/1.0.0/>) and extract it into `data/`. This gives `data/multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0/`, containing `MMASH.zip`. Extract `MMASH.zip` into a new folder named `MMASH` next to it, so that the data end up in `data/multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0/MMASH/DataPaper/user_1/…`. (`MMASH.zip` itself starts at `DataPaper/`, so the `MMASH` folder has to be created; some unzip tools do this automatically, others do not.) You can check `MMASH.zip` against PhysioNet's `SHA256SUMS.txt` in the same folder.
2. Install the Python packages: `pip install -r requirements.txt`.
3. In R, install the packages: `install.packages(c("tidyverse", "mgcv", "here", "knitr", "rmarkdown"))`.
4. Run the whole pipeline from the repository root (Git Bash on Windows):

   ```bash
   ./run_all.sh
   ```

   If `python` or `quarto` is not on your PATH, set it, for example: `PYTHON=python3 QUARTO=/path/to/quarto ./run_all.sh`.

The first step stops if any input CSV differs from `docs/data_manifest.sha256`. All numbers in the report are computed when it is rendered; none are typed by hand.

## Validation

See [docs/VALIDATION_AND_REPRODUCIBILITY.md](docs/VALIDATION_AND_REPRODUCIBILITY.md) for the checks performed and the fresh-run comparison.

## Limitations

The sample is small (n = 22, men only, one 24-h recording each). Clock time is not circadian phase: there is no dim-light melatonin onset (DLMO) or core body temperature, so the 24-h profile mixes endogenous rhythm with behaviour such as sleep, posture, activity and meals. Sleep periods are actigraphy estimates, not polysomnography. The intervals are computed by the Polar H7 device, not taken from raw ECG, and about a quarter of each recording is missing in regular gaps. Wake windows include physical activity, which was not modelled. GAMM p-values are approximate, and between-person effects such as chronotype rest on 22 people. All analyses are exploratory and do not support causal claims.

## Data availability

The raw data are available from PhysioNet under ODbL v1.0 ([doi:10.13026/cerq-fc86](https://doi.org/10.13026/cerq-fc86)). The summary tables in `output/tables/` are derived from MMASH and are shared under the same licence, with attribution to Rossi et al. (2020).
