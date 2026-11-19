"""Builds the sample database with its two views.

Usage:
    python build_database.py                 writes company.db next to this script (REPLACES it)
    python build_database.py other_name.db   writes a different file, leaving company.db alone

The data is seeded, so every run produces the same database.
"""
import random
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / "company.db"

random.seed(42)

NAMES = ["Ali", "Sara", "Reza", "Mina", "Omid", "Nima", "Hana", "Kian", "Leila", "Arash",
         "Dara", "Roya", "Sina", "Tara", "Babak", "Neda", "Farid", "Yasi", "Pouya", "Elham"]
DEPARTMENTS = ["Retail", "Online", "Wholesale"]
PRODUCTS = ["Laptop", "Phone", "Tablet", "Monitor", "Keyboard"]
N_SALES = 400

STRUCTURE = """
DROP VIEW IF EXISTS employees_list;
DROP VIEW IF EXISTS employee_sales;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS employees;

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    employee_name TEXT NOT NULL,
    department TEXT NOT NULL
);
CREATE TABLE sales (
    sale_id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    product TEXT NOT NULL,
    amount REAL NOT NULL,
    sale_date TEXT NOT NULL
);
CREATE VIEW employee_sales AS
SELECT e.employee_id, e.employee_name, e.department,
       s.product, s.amount, s.sale_date
FROM employees e JOIN sales s ON e.employee_id = s.employee_id;
CREATE VIEW employees_list AS
SELECT employee_id, employee_name, department FROM employees;
"""


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(STRUCTURE)
    for i, name in enumerate(NAMES, 1):
        conn.execute("INSERT INTO employees VALUES (?,?,?)", (i, name, random.choice(DEPARTMENTS)))
    for _ in range(N_SALES):
        conn.execute(
            "INSERT INTO sales (employee_id, product, amount, sale_date) VALUES (?,?,?,?)",
            (random.randint(1, len(NAMES)), random.choice(PRODUCTS),
             round(random.uniform(50, 2000), 2),
             f"2026-{random.randint(1, 10):02d}-{random.randint(1, 28):02d}"))
    conn.commit()

    print("Built:", DB_PATH)
    print("objects:", conn.execute("SELECT name, type FROM sqlite_master ORDER BY type, name").fetchall())
    print("employees:", conn.execute("SELECT COUNT(*) FROM employees_list").fetchone()[0],
          "| sales:", conn.execute("SELECT COUNT(*) FROM employee_sales").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
