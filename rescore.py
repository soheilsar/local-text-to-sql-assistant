"""Re-score saved results with the current scorer (scoring.py). No model is called.

Each result file in results/ stores the SQL the model wrote. This script runs that
SQL again on company.db, compares it with the gold result using scoring.py, and
rewrites the JSON files, the per-model reports and summary.csv.

Usage:
    python rescore.py
"""
import csv
import json

import compare_prompts as cp
from scoring import SCORER_VERSION

files = sorted(cp.RESULTS_DIR.glob("*__[ABC]_*.json"))
if not files:
    raise SystemExit(f"No result files found in {cp.RESULTS_DIR}")

csv_rows, models = [], []
print(f"{'file':<58}{'regular before':>16}{'after':>8}")
for path in files:
    run = json.loads(path.read_text(encoding="utf-8"))
    before = run["summary"]["regular"][0]
    for row in run["rows"]:
        if row["note"] == cp.TIMEOUT_NOTE:      # no SQL exists, stays failed
            continue
        result, error = cp.execute(row["sql"])
        row["ok"], row["note"] = cp.score(result, error, row["gold"])
    run["scorer"] = SCORER_VERSION
    run["db"] = cp.db_fingerprint()
    run["summary"] = cp.summarize(run["rows"])
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_rows.append(cp.summary_csv_row(run["timestamp"], run["model"], run["condition"],
                                       SCORER_VERSION, run["summary"]))
    if run["model"] not in models:
        models.append(run["model"])
    print(f"{path.name:<58}{before:>10}/{run['summary']['regular'][1]:<5}{run['summary']['regular'][0]:>3}")

with (cp.RESULTS_DIR / "summary.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(cp.CSV_HEADER)
    w.writerows(csv_rows)

for model in models:
    cp.build_report(model)
print("\nRewrote the result files, summary.csv and the reports.")
