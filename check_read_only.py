"""Proves the read-only layer works. Runs on a temporary COPY of the database,
so even if the protection were broken, the real company.db cannot be damaged."""
import shutil
import sqlite3
import tempfile
from pathlib import Path

import sql_assistant

with tempfile.TemporaryDirectory() as tmp:
    copy = Path(tmp) / "company_copy.db"
    shutil.copy(sql_assistant.DB_PATH, copy)
    sql_assistant.DB_PATH = copy          # run_query reads this at call time

    before = sql_assistant.run_query("SELECT COUNT(*) FROM sales")[1][0][0]
    try:
        sql_assistant.run_query("DELETE FROM sales")
        print("write attempt raised no error")
    except sqlite3.Error as e:
        print("write attempt raised:", e)
    except Exception as e:
        print("unexpected error type:", type(e).__name__, e)
    after = sql_assistant.run_query("SELECT COUNT(*) FROM sales")[1][0][0]

    print(f"sales rows before: {before}, after: {after}")
    if before == after:
        print("OK: row count unchanged, writes are blocked")
    else:
        print("PROBLEM: data was deleted, the read-only protection is NOT working")
