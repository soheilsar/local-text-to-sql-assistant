"""Three-condition prompt experiment for ONE model.

  A  baseline      database described in words only (no schema, no rules)
  B  schema        A + exact views, columns and allowed values
  C  schema_rules  B + the rules

Same database (company.db), same 25 questions (dev + held-out), same settings
(temperature 0, seed 42) for every run. Prompts live in prompts.py.

Usage:
    python compare_prompts.py --model qwen3:1.7b
    python compare_prompts.py --model qwen3:1.7b --limit 3      # smoke test, saves nothing
    python compare_prompts.py --model qwen3:1.7b --conditions B C

Output (folder results/):
    <model>__A_baseline.json, <model>__B_schema.json, <model>__C_schema_rules.json
    <model>__report.md      readable side-by-side report of all conditions run so far
    summary.csv             one line per (model, condition) run
"""
import argparse
import csv
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests

from dev_tests import DEV_TESTS
from heldout_tests import HELDOUT_TESTS
from prompts import CONDITIONS, LABELS, build_messages, system_prompt
from scoring import SCORER_VERSION, same_result
from sql_assistant import OLLAMA_URL, extract_sql, is_safe, run_query

RESULTS_DIR = Path(__file__).resolve().parent / "results"
SEED = 42
TIMEOUT = 600   # seconds per call; 4B models on a 4 GB GPU can be slow
TIMEOUT_NOTE = "model call timed out"

QUESTIONS = [("dev", t) for t in DEV_TESTS] + [("heldout", t) for t in HELDOUT_TESTS]


def safe_name(model):
    """'qwen3:1.7b' -> 'qwen3-1.7b' (':' and '/' are not allowed in Windows file names)."""
    return model.replace(":", "-").replace("/", "-")


def chat(model, messages):
    payload = {
        "model": model,
        "messages": messages,
        "think": False,
        "stream": False,
        "options": {"temperature": 0, "seed": SEED},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
    if r.status_code == 400 and "think" in r.text.lower():
        payload.pop("think")            # this model does not accept the think flag
        r = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["message"]["content"]


def db_fingerprint():
    n, total = run_query("SELECT COUNT(*), ROUND(SUM(amount), 2) FROM employee_sales")[1][0]
    return f"{n} sales, total amount {total}"


def execute(sql):
    """Safety filter + read-only execution, as in the assistant. Returns (result, error)."""
    if not is_safe(sql):
        return None, "blocked by is_safe"
    try:
        return run_query(sql), None
    except sqlite3.Error as e:
        return None, str(e)


def score(result, error, gold):
    """Returns (ok, note). Comparison rules are in scoring.py."""
    if gold is None:                    # adversarial: the right outcome is a refusal or an error
        return result is None, (error or "query ran, should have been refused")
    try:
        _, gold_rows = run_query(gold)
    except sqlite3.Error as e:
        return False, f"GOLD SQL ERROR: {e}"
    if result is None:
        return False, error
    ok = same_result(result[1], gold_rows)
    return ok, "" if ok else "different result"


def run_condition(model, cond, limit):
    rows = []
    questions = QUESTIONS[:limit]
    for i, (set_name, t) in enumerate(questions, 1):
        t0 = time.perf_counter()
        raw, sql = "", ""
        try:
            raw = chat(model, build_messages(cond, t["q"]))
        except requests.exceptions.Timeout:
            ok, note = False, TIMEOUT_NOTE
        else:
            sql = extract_sql(raw)
            result, error = execute(sql)
            ok, note = score(result, error, t["gold"])
        secs = time.perf_counter() - t0
        rows.append({"set": set_name, "question": t["q"], "gold": t["gold"], "raw": raw,
                     "sql": sql, "ok": bool(ok), "note": note, "seconds": round(secs, 2)})
        print(f"  [{cond}] {i:>2}/{len(questions)} {'PASS' if ok else 'FAIL'} {secs:4.1f}s  {t['q']}")
    return rows


def summarize(rows):
    def count(pred):
        sub = [r for r in rows if pred(r)]
        return [sum(r["ok"] for r in sub), len(sub)]
    return {
        "dev": count(lambda r: r["set"] == "dev"),
        "heldout": count(lambda r: r["set"] == "heldout"),
        "regular": count(lambda r: r["gold"] is not None),
        "adversarial": count(lambda r: r["gold"] is None),
        "total": count(lambda r: True),
        "avg_seconds": round(sum(r["seconds"] for r in rows) / max(len(rows), 1), 2),
    }


def fmt(pair):
    return f"{pair[0]}/{pair[1]}"


def build_report(model):
    safe = safe_name(model)
    runs = {}
    for key, name in CONDITIONS.items():
        p = RESULTS_DIR / f"{safe}__{key}_{name}.json"
        if p.exists():
            runs[key] = json.loads(p.read_text(encoding="utf-8"))
    if not runs:
        return None

    first = next(iter(runs.values()))
    out = [f"# {model}: three prompt conditions", "",
           f"- Database: {first['db']}",
           f"- Settings: temperature 0, seed {first['seed']}, no few-shot examples",
           f"- Questions: {first['summary']['total'][1]} (dev + held-out)",
           f"- Scoring: {first.get('scorer', 'v1 (positional columns, ordered rows)')}", "",
           "## Scores", "",
           "| Condition | Dev | Held-out | Regular questions | Adversarial | Total | Seconds per question |",
           "|---|---|---|---|---|---|---|"]
    for key, run in runs.items():
        s = run["summary"]
        out.append(f"| {LABELS[key]} | {fmt(s['dev'])} | {fmt(s['heldout'])} | {fmt(s['regular'])} | "
                   f"{fmt(s['adversarial'])} | {fmt(s['total'])} | {s['avg_seconds']} |")
    out += ["", "Adversarial questions count as passed when the query was blocked or raised an error, "
            "which at condition A can happen by accident (invented column names).", "",
            "## Every question", ""]

    by_cond = {k: {r["question"]: r for r in run["rows"]} for k, run in runs.items()}
    for n, row in enumerate(first["rows"], 1):
        out += [f"### {n}. [{row['set']}] {row['question']}", "",
                "Gold: " + ("(must be refused)" if row["gold"] is None else f"`{row['gold']}`"), ""]
        for key in runs:
            r = by_cond[key].get(row["question"])
            if r is None:
                continue
            note = f" ({r['note']})" if r["note"] else ""
            out += [f"**{LABELS[key]}: {'PASS' if r['ok'] else 'FAIL'}**{note}", "",
                    "```sql", r["sql"] or "(empty)", "```", ""]

    out += ["## Prompts sent", ""]
    for key in runs:
        out += [f"### {LABELS[key]}", "", "```text", system_prompt(key), "```", ""]

    path = RESULTS_DIR / f"{safe}__report.md"
    path.write_text("\n".join(out), encoding="utf-8")
    return path


CSV_HEADER = ["timestamp", "model", "condition", "scorer", "dev", "heldout", "regular",
              "adversarial", "total", "avg_seconds"]


def summary_csv_row(timestamp, model, condition, scorer, summary):
    return [timestamp, model, condition, scorer.split(":")[0], fmt(summary["dev"]), fmt(summary["heldout"]),
            fmt(summary["regular"]), fmt(summary["adversarial"]), fmt(summary["total"]), summary["avg_seconds"]]


def append_summary_csv(model, cond, summary):
    path = RESULTS_DIR / "summary.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_HEADER)
        w.writerow(summary_csv_row(datetime.now().isoformat(timespec="seconds"), model,
                                   f"{cond}_{CONDITIONS[cond]}", SCORER_VERSION, summary))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run prompt conditions A/B/C for one Ollama model.")
    ap.add_argument("--model", required=True, help="exact name from `ollama list`")
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=list(CONDITIONS))
    ap.add_argument("--limit", type=int, default=len(QUESTIONS), help="only the first N questions (smoke test)")
    args = ap.parse_args(argv)
    save = args.limit >= len(QUESTIONS)

    # Warm-up: loads the model into memory so the first timed question is not slower than the rest.
    try:
        chat(args.model, [{"role": "user", "content": "Reply with only the word: ready"}])
    except requests.exceptions.ConnectionError:
        raise SystemExit(f"Cannot reach Ollama at {OLLAMA_URL}. Start Ollama and try again.")
    except requests.exceptions.HTTPError as e:
        raise SystemExit(f"Ollama rejected the model '{args.model}' ({e}). Check the exact name with: ollama list")

    fingerprint = db_fingerprint()
    print(f"Model: {args.model} | database: {fingerprint}")
    table = []
    for cond in args.conditions:
        print(f"\nCondition {LABELS[cond]}")
        rows = run_condition(args.model, cond, args.limit)
        summary = summarize(rows)
        table.append((cond, summary))
        if save:
            RESULTS_DIR.mkdir(exist_ok=True)
            run = {"model": args.model, "condition": f"{cond}_{CONDITIONS[cond]}", "seed": SEED,
                   "db": fingerprint, "scorer": SCORER_VERSION, "timestamp": datetime.now().isoformat(timespec="seconds"),
                   "system_prompt": system_prompt(cond), "summary": summary, "rows": rows}
            path = RESULTS_DIR / f"{safe_name(args.model)}__{cond}_{CONDITIONS[cond]}.json"
            path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
            append_summary_csv(args.model, cond, summary)

    print(f"\n{args.model}")
    print(f"{'condition':<32}{'dev':>7}{'heldout':>9}{'regular':>9}{'adversarial':>13}{'total':>8}{'s/q':>7}")
    for cond, s in table:
        print(f"{LABELS[cond]:<32}{fmt(s['dev']):>7}{fmt(s['heldout']):>9}{fmt(s['regular']):>9}"
              f"{fmt(s['adversarial']):>13}{fmt(s['total']):>8}{s['avg_seconds']:>7}")
    if save:
        report = build_report(args.model)
        print(f"\nSaved to {RESULTS_DIR}. Report: {report}")
    else:
        print("\nSmoke test (--limit): nothing saved.")


if __name__ == "__main__":
    main()
