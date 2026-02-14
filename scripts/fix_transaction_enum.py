"""Fix evotransactiontype enum to have uppercase values."""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

# Add uppercase values to evotransactiontype enum
values_to_add = ["TASK_REWARD", "ADMIN_CREDIT", "ADMIN_DEBIT"]
for val in values_to_add:
    try:
        cur.execute(f"ALTER TYPE evotransactiontype ADD VALUE IF NOT EXISTS '{val}';")
        print(f"Added {val}")
    except Exception as e:
        print(f"Error adding {val}: {e}")

print("Done!")
cur.close()
conn.close()
