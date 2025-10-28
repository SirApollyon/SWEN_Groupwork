import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pymssql
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT ---
load_dotenv()

# --- CONFIGURATION ---
TIME_RANGE = "12_months"  # Options: "ytd", "12_months", "3_years", "5_years", or ("YYYY-MM-DD", "YYYY-MM-DD")

def get_db_credentials():
    server = os.getenv("AZURE_SQL_SERVER")
    database = os.getenv("AZURE_SQL_DB")
    user = os.getenv("AZURE_SQL_USER")
    password = os.getenv("AZURE_SQL_PASSWORD")
    port = int(os.getenv("AZURE_SQL_PORT", "1433"))

    missing = [k for k, v in {
        "AZURE_SQL_SERVER": server,
        "AZURE_SQL_DB": database,
        "AZURE_SQL_USER": user,
        "AZURE_SQL_PASSWORD": password
    }.items() if not v]

    if missing:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

    return server, database, user, password, port

# --- TIME RANGE LOGIC ---
def get_date_range(option):
    today = datetime.utcnow()
    if option == "ytd":
        start = datetime(today.year, 1, 1)
    elif option == "12_months":
        start = today - timedelta(days=365)
    elif option == "3_years":
        start = today - timedelta(days=3 * 365)
    elif option == "5_years":
        start = today - timedelta(days=5 * 365)
    elif isinstance(option, tuple) and len(option) == 2:
        start = datetime.strptime(option[0], "%Y-%m-%d")
        today = datetime.strptime(option[1], "%Y-%m-%d")
    else:
        raise ValueError("Invalid time range option")
    return start.date(), today.date()

# --- SQL QUERY BUILDER ---
def build_query(start_date, end_date):
    return f"""
        SELECT FORMAT([date], 'yyyy-MM') AS month,
               SUM(amount) AS total_expense
        FROM app.transactions
        WHERE [type] = 'expense'
          AND [date] BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY FORMAT([date], 'yyyy-MM')
        ORDER BY month;
    """

# --- FETCH DATA ---
def fetch_data(query, server, database, user, password, port):
    try:
        with pymssql.connect(server=server, user=user, password=password, database=database, port=port) as conn:
            df = pd.read_sql(query, conn)
        return df
    except pymssql.Error as e:
        raise ConnectionError(f"Database connection failed: {e}")

# --- PLOT ---
def plot_expenses(df, start_date, end_date):
    if df.empty:
        print("No expense data found for the selected time range.")
        return

    plt.figure(figsize=(12, 6))
    plt.bar(df['month'], df['total_expense'], color='salmon')
    plt.xticks(rotation=45, ha='right')
    plt.ylabel("CHF")
    plt.xlabel("Month")
    plt.title(f"Monthly Expenses ({start_date} to {end_date})")
    plt.tight_layout()
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.show()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    try:
        server, database, user, password, port = get_db_credentials()
        start_date, end_date = get_date_range(TIME_RANGE)
        query = build_query(start_date, end_date)
        df = fetch_data(query, server, database, user, password, port)
        plot_expenses(df, start_date, end_date)
    except Exception as ex:
        print(f"❌ Error: {ex}")