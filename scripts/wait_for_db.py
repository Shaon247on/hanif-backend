"""Wait for database to be ready before starting Django."""
import os
import sys
import time

import psycopg


def wait_for_db(max_retries: int = 30, delay: float = 1.0) -> None:
    """Wait for PostgreSQL to accept connections."""
    database_url = os.environ.get("DATABASE_URL", "")

    if "sqlite" in database_url or not database_url:
        print("Using SQLite — no wait needed.")
        return

    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg.connect(database_url)
            conn.close()
            print(f"✅ Database ready (attempt {attempt})")
            return
        except psycopg.OperationalError:
            print(f"⏳ Database not ready (attempt {attempt}/{max_retries})...")
            time.sleep(delay)

    print("❌ Could not connect to database.")
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
