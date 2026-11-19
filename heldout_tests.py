# Held-out set: never tune the prompt on these questions.
# If you do, they become development questions; write fresh held-out ones.

HELDOUT_TESTS = [
    {"q": "How many Laptop sales were there?",
     "gold": "SELECT COUNT(*) FROM employee_sales WHERE product = 'Laptop'"},
    {"q": "Show the id and name of the 3 employees with the lowest total sales",
     "gold": "SELECT employee_id, employee_name FROM employee_sales GROUP BY employee_id, employee_name ORDER BY SUM(amount) ASC LIMIT 3"},
    {"q": "How much did Sara sell in total?",
     "gold": "SELECT SUM(amount) FROM employee_sales WHERE employee_name = 'Sara'"},
    {"q": "What is the average sale amount per department?",
     "gold": "SELECT department, AVG(amount) FROM employee_sales GROUP BY department"},
    {"q": "How many employees work in each department?",
     "gold": "SELECT department, COUNT(*) FROM employees_list GROUP BY department"},
    {"q": "Which product was sold the most times?",
     "gold": "SELECT product FROM employee_sales GROUP BY product ORDER BY COUNT(*) DESC LIMIT 1"},
    {"q": "How many sales did Omid make in August 2026?",
     "gold": "SELECT COUNT(*) FROM employee_sales WHERE employee_name = 'Omid' AND sale_date BETWEEN '2026-08-01' AND '2026-08-31'"},
    {"q": "What is the total sales amount for Laptops in the Online department?",
     "gold": "SELECT SUM(amount) FROM employee_sales WHERE product = 'Laptop' AND department = 'Online'"},
    {"q": "Which employee made the smallest single sale?",
     "gold": "SELECT employee_name FROM employee_sales ORDER BY amount ASC LIMIT 1"},
    {"q": "Which month of 2026 had the highest total sales? Answer in YYYY-MM format.",
     "gold": "SELECT strftime('%Y-%m', sale_date) FROM employee_sales GROUP BY 1 ORDER BY SUM(amount) DESC LIMIT 1"},
]