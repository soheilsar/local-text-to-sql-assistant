"""Result comparison used by the prompt experiment (scorer v2).

The old comparison in evaluate.py looked at the first N columns of the model's
result, in order, and demanded the same row order whenever the gold SQL had an
ORDER BY. That marked correct answers as failures, for example:

  - the model returns employee_id, employee_name where gold returns employee_name
  - the model returns amount, employee_name where gold returns employee_name, amount
  - the model returns the right 3 employees, but not in ranking order

Scorer v2 passes a result when SOME choice of the model's columns, in SOME order,
reproduces the gold rows. Rows are compared as an unordered collection. Row COUNT
still has to match, so "all employees" never passes for "the lowest 3".

Trade-off: a top-N list in the wrong order passes if it contains the right N rows.
"""
from collections import Counter
from itertools import permutations
from math import perm

SCORER_VERSION = "v2: column order, extra columns and row order ignored"
MAX_COLUMN_CHOICES = 50_000     # safety limit for very wide results


def _norm(value):
    return round(value, 2) if isinstance(value, float) else value


def same_result(model_rows, gold_rows):
    if not gold_rows:
        return not model_rows
    if not model_rows or len(model_rows) != len(gold_rows):
        return False
    gold_width, model_width = len(gold_rows[0]), len(model_rows[0])
    if model_width < gold_width or perm(model_width, gold_width) > MAX_COLUMN_CHOICES:
        return False
    gold = Counter(tuple(_norm(v) for v in row) for row in gold_rows)
    for cols in permutations(range(model_width), gold_width):
        got = Counter(tuple(_norm(row[i]) for i in cols) for row in model_rows)
        if got == gold:
            return True
    return False
