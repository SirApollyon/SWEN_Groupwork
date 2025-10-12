-- Schema anlegen (falls nicht vorhanden)
IF SCHEMA_ID('app') IS NULL
    EXEC('CREATE SCHEMA app');
GO

/* =========================
   USERS
   ========================= */
IF OBJECT_ID('app.users') IS NULL
BEGIN
    CREATE TABLE app.users (
        user_id        INT IDENTITY(1,1) PRIMARY KEY,
        name           NVARCHAR(255)       NULL,
        email          NVARCHAR(255)       NOT NULL,
        creation_date  DATETIME2           NOT NULL CONSTRAINT DF_users_creation_date DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_users_email UNIQUE (email)
    );
END
GO

/* =========================
   ACCOUNTS
   ========================= */
IF OBJECT_ID('app.accounts') IS NULL
BEGIN
    CREATE TABLE app.accounts (
        account_id     INT IDENTITY(1,1) PRIMARY KEY,
        user_id        INT                 NOT NULL,
        account_name   NVARCHAR(200)       NOT NULL,
        balance        DECIMAL(18,2)       NOT NULL CONSTRAINT DF_accounts_balance DEFAULT (0),
        currency       NCHAR(3)            NOT NULL CONSTRAINT DF_accounts_currency DEFAULT N'CHF',
        created_at     DATETIME2           NOT NULL CONSTRAINT DF_accounts_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_accounts_user
            FOREIGN KEY (user_id) REFERENCES app.users(user_id)
            ON DELETE CASCADE
    );

    CREATE INDEX IX_accounts_user ON app.accounts(user_id);
    CREATE UNIQUE INDEX UQ_accounts_user_name ON app.accounts(user_id, account_name);
END
GO

/* =========================
   CATEGORIES
   ========================= */
IF OBJECT_ID('app.categories') IS NULL
BEGIN
    CREATE TABLE app.categories (
        category_id    INT IDENTITY(1,1) PRIMARY KEY,
        user_id        INT                 NOT NULL,
        name           NVARCHAR(100)       NOT NULL,
        [type]         NVARCHAR(20)        NOT NULL, -- 'expense' | 'income'
        created_at     DATETIME2           NOT NULL CONSTRAINT DF_categories_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_categories_user
            FOREIGN KEY (user_id) REFERENCES app.users(user_id)
            ON DELETE CASCADE,
        CONSTRAINT CK_categories_type
            CHECK ([type] IN (N'expense', N'income')),
        CONSTRAINT UQ_categories_user_name UNIQUE (user_id, name, [type])
    );

    CREATE INDEX IX_categories_user ON app.categories(user_id);
END
GO

/* =========================
   TRANSACTIONS (ohne user_id)
   ========================= */
IF OBJECT_ID('app.transactions') IS NULL
BEGIN
    CREATE TABLE app.transactions (
        transaction_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        account_id     INT                 NOT NULL,
        amount         DECIMAL(18,2)       NOT NULL,
        category_id    INT                 NULL,       -- optional
        [description]  NVARCHAR(500)       NULL,
        [date]         DATE                NOT NULL,
        [type]         NVARCHAR(20)        NOT NULL,   -- 'expense' | 'income'
        currency       NCHAR(3)            NOT NULL CONSTRAINT DF_transactions_currency DEFAULT N'CHF',
        created_at     DATETIME2           NOT NULL CONSTRAINT DF_transactions_created_at DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_transactions_account
            FOREIGN KEY (account_id) REFERENCES app.accounts(account_id)
            ON DELETE CASCADE,

        -- WICHTIG: KEINE Cascade-Action hier, um multiple Pfade zu vermeiden
        CONSTRAINT FK_transactions_category
            FOREIGN KEY (category_id) REFERENCES app.categories(category_id),

        CONSTRAINT CK_transactions_type
            CHECK ([type] IN (N'expense', N'income')),
        CONSTRAINT CK_transactions_amount
            CHECK (amount >= 0)
    );

    CREATE INDEX IX_transactions_account_date ON app.transactions(account_id, [date]);
    CREATE INDEX IX_transactions_category     ON app.transactions(category_id);
END
GO

/* =========================
   BUDGETS (ohne user_id)
   ========================= */
IF OBJECT_ID('app.budgets') IS NULL
BEGIN
    CREATE TABLE app.budgets (
        budget_id      INT IDENTITY(1,1) PRIMARY KEY,
        category_id    INT                 NOT NULL,
        amount         DECIMAL(18,2)       NOT NULL,
        [month]        DATE                NOT NULL,   -- 1. des Monats
        created_at     DATETIME2           NOT NULL CONSTRAINT DF_budgets_created_at DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_budgets_category
            FOREIGN KEY (category_id) REFERENCES app.categories(category_id)
            ON DELETE CASCADE,

        CONSTRAINT CK_budgets_amount
            CHECK (amount >= 0),
        CONSTRAINT CK_budgets_month_first_day
            CHECK (DAY([month]) = 1),
        CONSTRAINT UQ_budgets_cat_month
            UNIQUE (category_id, [month])
    );

    CREATE INDEX IX_budgets_cat_month ON app.budgets(category_id, [month]);
END
GO