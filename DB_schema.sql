# Users
cursor.execute("""
CREATE TABLE IF NOT EXISTS Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    currency TEXT DEFAULT 'CHF',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
""")

# Accounts
cursor.execute("""
CREATE TABLE IF NOT EXISTS Accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('Bank', 'CreditCard', 'Cash')),
    balance REAL DEFAULT 0.00,
    currency TEXT DEFAULT 'CHF',
    FOREIGN KEY(user_id) REFERENCES Users(user_id)
);
""")

# Categories
cursor.execute("""
CREATE TABLE IF NOT EXISTS Categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('Income', 'Expense'))
);
""")

# Transactions
cursor.execute("""
CREATE TABLE IF NOT EXISTS Transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    category_id INTEGER,
    amount REAL NOT NULL,
    description TEXT,
    date TEXT NOT NULL,
    type TEXT CHECK(type IN ('Income', 'Expense')),
    FOREIGN KEY(account_id) REFERENCES Accounts(account_id),
    FOREIGN KEY(category_id) REFERENCES Categories(category_id)
);
""")
