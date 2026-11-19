import re
import sqlite3
import requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:1.7b"
DB_PATH = Path(__file__).resolve().parent / "company.db"
MAX_ROWS = 50
MAX_RETRIES = 0   # repair loop is off by default: it did not help at 1.7B

SCHEMA = """
View employee_sales: one row per sale.
  columns: employee_id, employee_name, department, product, amount, sale_date
  amount is the sale value; sale_date format is YYYY-MM-DD
View employees_list: one row per employee. Names and departments only; it has NO sales data (no amount, product or sale_date).
  columns: employee_id, employee_name, department
"""

# Note the leading f: without it, {SCHEMA} is sent to the model as literal text.
SYSTEM_PROMPT = f"""You are a SQL assistant for a SQLite database.
Convert the user's question into exactly one SQLite SELECT statement.

{SCHEMA}

Rules:
- Query ONLY the views employee_sales and employees_list. Never use any other table.
- To list employees when no sales figures are needed, use employees_list.
- For anything involving sales, amounts, products or dates, use employee_sales.
- Return ONLY the SQL statement. No explanation, no markdown, no comments.
- When listing employees, always include both employee_id and employee_name.
- Questions that start with "How many" use COUNT(*), even if they also contain the word "total". Questions about money, revenue or amounts use SUM(amount).
- Use LIMIT when the user asks for a top N.
- If the question asks for the single highest, lowest or best item (for example "which department has the most sales"), return only that row using LIMIT 1. If the question gives a number N, use LIMIT N.
"""

# Few-shot examples: (question, sql) pairs. Never reuse a test question here.
EXAMPLES = [
    ("Which 3 products have the highest total sales amount?",
     "SELECT product, SUM(amount) AS total_sales FROM employee_sales "
     "GROUP BY product ORDER BY total_sales DESC LIMIT 3"),
    ("Show Laptop sales above 1500 in March 2026",
     "SELECT employee_name, amount, sale_date FROM employee_sales "
     "WHERE product = 'Laptop' AND amount > 1500 "
     "AND sale_date BETWEEN '2026-03-01' AND '2026-03-31' ORDER BY sale_date"),
    ("How many sales did the Online department make?",
     "SELECT COUNT(*) AS sale_count FROM employee_sales WHERE department = 'Online'"),
]


def build_messages(question):
    """System prompt, then each example as a fake user/assistant exchange, then the real question."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for q, sql in EXAMPLES:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": sql})
    messages.append({"role": "user", "content": question})
    return messages


def chat(messages):
    """Send a message list to Ollama and return the reply text."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "think": False,
        "stream": False,
        "options": {"temperature": 0},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


def extract_sql(text):
    """Remove <think> blocks and markdown fences, keep only the SQL."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1)
    return text.strip()


def is_safe(sql):
    """First safety layer: one SELECT statement, no write keywords."""
    s = sql.strip().rstrip(";").strip()
    if not s.lower().startswith("select"):
        return False
    if ";" in s:                      # a second statement hiding after the first
        return False
    if re.search(r"\b(insert|update|delete|drop|alter|attach|pragma|create|replace)\b", s, re.IGNORECASE):
        return False
    return True


def run_query(sql):
    """Second (real) safety layer: a read-only connection. Returns (columns, rows)."""
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
        return cols, rows
    finally:
        conn.close()


def generate_and_run(question, retries=MAX_RETRIES):
    """Returns (sql, result, error). result is (columns, rows) or None."""
    messages = build_messages(question)
    for attempt in range(retries + 1):
        sql = extract_sql(chat(messages))
        if not is_safe(sql):
            return sql, None, "blocked by is_safe"      # final: never retried
        try:
            return sql, run_query(sql), None
        except sqlite3.Error as e:
            if attempt == retries:
                return sql, None, str(e)
            messages.append({"role": "assistant", "content": sql})
            messages.append({"role": "user", "content":
                f"That SQL failed with this error: {e}. "
                "Return a corrected SQLite SELECT statement only."})

def main():
    print("Type a question, or press Enter to quit.")
    while True:
        question = input("\nAsk: ").strip()
        if not question:
            break
        sql, result, error = generate_and_run(question)
        print("SQL:", sql)
        if result is None:
            print("Could not answer:", error)
            continue
        cols, rows = result
        print(cols)
        for row in rows:
            print(row)

        


if __name__ == "__main__":
    main()


