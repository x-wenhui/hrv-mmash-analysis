#!/usr/bin/env bash
# Run the full pipeline from the raw MMASH files to the rendered report.
# Override tool paths if needed, e.g.  PYTHON=python3 QUARTO=/path/to/quarto ./run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python}"
RSCRIPT="${RSCRIPT:-Rscript}"
QUARTO="${QUARTO:-quarto}"
# Record the PDF's creation time in UTC rather than the local time zone.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"

"$PYTHON" python/00_check_data.py
"$PYTHON" python/01_clean_rr.py
"$PYTHON" python/02_hrv_windows.py
"$PYTHON" python/03_sleep_wake.py
"$RSCRIPT" R/04_gamm.R
"$RSCRIPT" R/05_panas.R
"$QUARTO" render report/report.qmd
