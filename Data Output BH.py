import pyodbc
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# --- CONFIG ---
DB_CONN_STR = "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=yes;"
TIME_RANGE = "12_months"  # Options: "ytd", "12_months", "3_years", "5_years", or ("YYYY-MM-DD", "YYYY-MM-DD")

# --- TIME RANGE LOGIC ---
def get_date_range(option):
    today = datetime.utcnow()
    if option == "ytd":
        start = datetime(today.year, 1, 1)
    elif option == "12_months":
        start = today - timedelta(days=365)
    elif option == "3_years":
        start = today - timedelta(days=3*365)
    elif option == "5_years":
        start = today - timedelta(days=5*365)
    elif isinstance(option, tuple):
        start = datetime.strptime(option[0], "%Y-%m-%d")
        today = datetime.strptime(option[1], "%Y-%m-%d")
    else:
        raise ValueError("Invalid time range option")
    return start.date(), today.date()

start_date, end_date = get_date_range(TIME_RANGE)

# --- SQL QUERY ---
query = f"""
SELECT 
    FORMAT([date], 'yyyy-MM') AS month,
    SUM(amount) AS total_expense
FROM app.transactions
WHERE [type] = 'expense'
  AND [date] BETWEEN '{start_date}' AND '{end_date}'
GROUP BY FORMAT([date], 'yyyy-MM')
ORDER BY month;
"""

# --- FETCH DATA ---
conn = pyodbc.connect(DB_CONN_STR)
df = pd.read_sql(query, conn)
conn.close()

# --- PLOT ---
plt.figure(figsize=(12, 6))
plt.bar(df['month'], df['total_expense'], color='salmon')
plt.xticks(rotation=45, ha='right')
plt.ylabel("CHF")
plt.xlabel("Month")
plt.title(f"Monthly Expenses ({start_date} to {end_date})")
plt.tight_layout()
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.show()