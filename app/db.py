import os
from dotenv import load_dotenv
import pymssql

# Load environment variables (.env)
load_dotenv()

SERVER = os.getenv("AZURE_SQL_SERVER")
DATABASE = os.getenv("AZURE_SQL_DB")
USER = os.getenv("AZURE_SQL_USER")
PWD = os.getenv("AZURE_SQL_PASSWORD")
PORT = int(os.getenv("AZURE_SQL_PORT", "1433"))

CONNECT_KW = dict(
    server=SERVER,
    user=USER,
    password=PWD,
    database=DATABASE,
    port=PORT,
    timeout=30,
    login_timeout=30,
    tds_version="7.4",
)

def insert_receipt(user_id: int, content: bytes):
    """Insert an image file into app.receipts as VARBINARY(MAX)."""
    if not content:
        raise ValueError("Empty file content")
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            # Check if user exists (foreign key constraint)
            cur.execute("SELECT 1 FROM app.users WHERE user_id=%s", (user_id,))
            if not cur.fetchone():
                raise ValueError("Unknown user_id")

            # Insert record; status_id will default to 1 ('pending')
            cur.execute(
                """
                INSERT INTO app.receipts (user_id, receipt_image)
                OUTPUT INSERTED.receipt_id, INSERTED.upload_date, INSERTED.status_id
                VALUES (%s, %s)
                """,
                (user_id, pymssql.Binary(content)),
            )
            row = cur.fetchone()
            conn.commit()
            return {
                "receipt_id": row["receipt_id"],
                "upload_date": row["upload_date"].isoformat(),
                "status_id": row["status_id"],
            }
def test_connection():
    """Simple connection test."""
    try:
        with pymssql.connect(**CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT GETDATE()")
                print("DB connection OK:", cur.fetchone()[0])
    except Exception as e:
        print("DB connection failed:", e)
