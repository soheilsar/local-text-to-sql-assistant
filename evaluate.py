import sqlite3
from sql_assistant import generate_and_run, run_query, MODEL
from dev_tests import DEV_TESTS
import time

start = time.perf_counter()

def normalize(rows):
    return [tuple(round(v, 2) if isinstance(v, float) else v for v in row) for row in rows]


def same_result(model_rows, gold_rows, ordered):
    width = len(gold_rows[0]) if gold_rows else 0
    model = normalize([row[:width] for row in model_rows])
    gold = normalize(gold_rows)
    if ordered:
        return model == gold
    return sorted(model, key=repr) == sorted(gold, key=repr)


def evaluate(tests=DEV_TESTS, retries=0):
    passed = 0
    for t in tests:
        sql, result, error = generate_and_run(t["q"], retries)
        ok, note = False, ""

        if t["gold"] is None:
            ok = result is None
            note = error or "query ran, should have been refused"
        else:
            try:
                _, gold_rows = run_query(t["gold"])
                if result is None:
                    note = error
                else:
                    ok = same_result(result[1], gold_rows, "order by" in t["gold"].lower())
                    if not ok:
                        note = "different result"
            except sqlite3.Error as e:
                note = f"GOLD SQL ERROR: {e}"

        passed += ok
        print(f"{'PASS' if ok else 'FAIL'} | {t['q']}")
        if not ok or t["gold"] is None:
            print(f"       SQL: {sql}")
            print(f"       note: {note}")

    print(f"\n{MODEL} (retries={retries}): {passed}/{len(tests)} passed, "f"{(time.perf_counter() - start) / len(tests):.1f}s per question")


if __name__ == "__main__":
    evaluate()
