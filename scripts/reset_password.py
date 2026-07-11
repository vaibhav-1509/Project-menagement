"""Recovery tool: resets a user's password hash directly against the DB,
bypassing the API (useful if the first Admin's password is lost).

Usage:
    python scripts/reset_password.py <username> <new_password>
"""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyodbc  # noqa: E402

from app.config import settings  # noqa: E402
from app.security import hash_password  # noqa: E402


def reset_password(username: str, new_password: str) -> None:
    conn_str = (
        f"DRIVER={{{settings.db_driver}}};"
        f"SERVER={settings.db_server},{settings.db_port};"
        f"DATABASE={settings.db_name};"
        f"UID={settings.db_user};"
        f"PWD={settings.db_password};"
        f"TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cursor = conn.cursor()
        # Also rotates SecurityStamp so any session token issued before this
        # reset stops working immediately, instead of remaining valid until
        # it naturally expires (see app/security.py's get_current_user).
        cursor.execute(
            "UPDATE Users SET PasswordHash = ?, SecurityStamp = ? WHERE Username = ?",
            hash_password(new_password),
            secrets.token_hex(32),
            username,
        )
        if cursor.rowcount == 0:
            print(f"No user named '{username}' found.")
        else:
            print(f"Password updated for '{username}'.")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/reset_password.py <username> <new_password>")
        raise SystemExit(1)
    reset_password(sys.argv[1], sys.argv[2])
