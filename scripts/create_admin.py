"""Creates the first Admin account via sql/001_schema.sql's sp_CreateFirstAdmin.

Generates a random password, hashes it with the same passlib context the API
uses to verify logins, and prints the plaintext password exactly once - it is
never written to disk.

Usage:
    python scripts/create_admin.py [username]
"""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyodbc  # noqa: E402

from app.config import settings  # noqa: E402
from app.security import hash_password  # noqa: E402

DEFAULT_USERNAME = "admin"


def _connect() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{{settings.db_driver}}};"
        f"SERVER={settings.db_server},{settings.db_port};"
        f"DATABASE={settings.db_name};"
        f"UID={settings.db_user};"
        f"PWD={settings.db_password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=True)


def create_first_admin(username: str) -> str | None:
    password = secrets.token_urlsafe(12)
    password_hash = hash_password(password)

    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("EXEC sp_CreateFirstAdmin @Username = ?, @PasswordHash = ?", username, password_hash)
    except pyodbc.Error as exc:
        if "already exists" in str(exc):
            print("An Admin account already exists - sp_CreateFirstAdmin only bootstraps the first one. Skipping.")
            return None
        raise
    finally:
        conn.close()

    return password


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USERNAME
    password = create_first_admin(username)
    if password:
        print()
        print("=" * 60)
        print(f"  Admin username: {username}")
        print(f"  Admin password: {password}")
        print("  Save this now - it will not be shown again.")
        print("=" * 60)
