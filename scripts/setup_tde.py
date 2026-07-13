r"""Enables Transparent Data Encryption (TDE) - at-rest encryption of the
database's own files on disk, on top of the in-transit TLS the app's
connection string already uses (Encrypt=yes). Requires SQL Server
Standard/Enterprise/Developer edition - Express does not support TDE.

Idempotent and safe to re-run:
  - If the server already has a master key/certificate (e.g. a fresh
    .\deploy.ps1 run after .\cleanup.ps1 dropped just the app database -
    cleanup.ps1 never touches `master`), those are reused as-is and only the
    per-database encryption key is (re)created for the new database.
  - If TDE is not supported on this SQL Server edition, prints a clear
    message and exits without changing anything - it does not abort the
    rest of deployment.

CRITICAL: the certificate this script creates is backed up to ./tde-backup/
the first time it's created. That backup - not the database itself - is the
only way to ever decrypt a native SQL Server backup (.bak) of this database
restored somewhere else, or recovered after this SQL Server instance's
`master` database is ever rebuilt from scratch. Losing it does NOT affect
the live database (which keeps working normally), but it does mean any old
.bak backup of it can never be restored anywhere again. Move that folder to
secure, offline storage - it is as sensitive as your database password.

Usage:
    python scripts/setup_tde.py
"""

import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyodbc  # noqa: E402

from app.config import settings  # noqa: E402

CERT_NAME = "PMT_TDE_Cert"
BACKUP_DIR = Path(__file__).resolve().parent.parent / "tde-backup"


def _connect(database: str) -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{{settings.db_driver}}};"
        f"SERVER={settings.db_server},{settings.db_port};"
        f"DATABASE={database};"
        f"UID={settings.db_user};"
        f"PWD={settings.db_password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=True)


def _master_key_exists(cursor) -> bool:
    cursor.execute("SELECT 1 FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##'")
    return cursor.fetchone() is not None


def _certificate_exists(cursor) -> bool:
    cursor.execute("SELECT 1 FROM sys.certificates WHERE name = ?", CERT_NAME)
    return cursor.fetchone() is not None


def _sql_literal(value: str) -> str:
    """CREATE MASTER KEY / BACKUP CERTIFICATE reject ODBC '?' parameter
    markers in their PASSWORD/FILE clauses (SQL Server parses these at a
    different stage than a normal parameterized query - `?` there raises
    'Incorrect syntax near @P1'), so these two statements must inline their
    literals instead. Safe here because every value passed through this is
    either our own secrets.token_urlsafe() output or a path this script
    itself built, never external/user input - this only guards against a
    stray quote breaking the statement, not against injection from outside."""
    return "'" + value.replace("'", "''") + "'"


def _database_encryption_key_exists(cursor, db_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sys.dm_database_encryption_keys dek "
        "JOIN sys.databases db ON db.database_id = dek.database_id WHERE db.name = ?",
        db_name,
    )
    return cursor.fetchone() is not None


def _archive_if_exists(path: Path) -> None:
    """BACKUP CERTIFICATE has no overwrite option - it fails outright if the
    target file already exists. That collides with a real scenario: SQL
    Server itself gets reinstalled fresh (so it has no memory of the old
    cert and this script creates a new one) while the project folder still
    has the OLD backup sitting in tde-backup/ from before. Move the stale
    file aside with a timestamp instead of colliding with it or silently
    overwriting a backup that might still be someone's only copy."""
    if not path.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archived = path.with_name(f"{path.stem}.superseded-{stamp}{path.suffix}")
    path.rename(archived)
    print(f"  Existing {path.name} found (from an earlier cert) - archived to {archived.name}")


def _write_backup_bundle(dmk_password: str, pvk_password: str) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    cert_file = BACKUP_DIR / "pmt_tde_cert.cer"
    pvk_file = BACKUP_DIR / "pmt_tde_cert.pvk"
    readme_file = BACKUP_DIR / "README.txt"
    _archive_if_exists(cert_file)
    _archive_if_exists(pvk_file)
    _archive_if_exists(readme_file)

    # Written to disk BEFORE the passwords are only ever shown on screen -
    # a console message can be missed or scrolled past, and there is no way
    # to recover a master key/certificate password after the fact the way
    # scripts/reset_password.py can recover a forgotten admin login.
    readme_file.write_text(
        "Transparent Data Encryption (TDE) backup for Project Management Tool\n"
        "======================================================================\n"
        f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n"
        "THESE FILES ARE AS SENSITIVE AS YOUR DATABASE PASSWORD - anyone who has\n"
        "them plus the passwords below can decrypt this database's data. Move this\n"
        "whole folder to secure, OFFLINE storage (password manager, encrypted USB\n"
        "drive) and then delete it from this machine once backed up elsewhere.\n"
        "deploy.ps1/cleanup.ps1 never read, write, or delete anything in this\n"
        "folder - nothing here happens automatically after this one-time setup.\n\n"
        "Files:\n"
        "  pmt_tde_cert.cer  - the certificate's public part\n"
        "  pmt_tde_cert.pvk  - the certificate's private key (itself encrypted)\n\n"
        "Passwords (only needed for disaster recovery on a DIFFERENT SQL Server\n"
        "instance - THIS instance already has everything applied and needs none\n"
        "of this for normal day-to-day operation):\n"
        f"  Master key password:        {dmk_password}\n"
        f"  Private key file password:  {pvk_password}\n\n"
        "To restore onto a different or rebuilt SQL Server instance (only ever\n"
        "needed to recover an old native SQL .bak backup of the encrypted database\n"
        "elsewhere - the running database itself does not need this):\n"
        "  USE master;\n"
        "  IF NOT EXISTS (SELECT 1 FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')\n"
        "      CREATE MASTER KEY ENCRYPTION BY PASSWORD = '<a new password of your choice>';\n"
        "  CREATE CERTIFICATE PMT_TDE_Cert\n"
        "      FROM FILE = 'C:\\path\\to\\pmt_tde_cert.cer'\n"
        "      WITH PRIVATE KEY (\n"
        "          FILE = 'C:\\path\\to\\pmt_tde_cert.pvk',\n"
        f"          DECRYPTION BY PASSWORD = '{pvk_password}'\n"
        "      );\n"
        "  -- Then RESTORE your .bak backup of the encrypted database as normal.\n",
        encoding="utf-8",
    )
    print(f"  TDE certificate + passwords backed up to: {BACKUP_DIR}")
    print("  ^ Move that folder to secure OFFLINE storage - it is not backed up anywhere else.")
    return cert_file, pvk_file


def setup_tde() -> None:
    master_conn = _connect("master")
    try:
        cursor = master_conn.cursor()

        dmk_password = None
        if not _master_key_exists(cursor):
            dmk_password = secrets.token_urlsafe(32)
            print("Creating database master key on this SQL Server instance...")
            cursor.execute(f"CREATE MASTER KEY ENCRYPTION BY PASSWORD = {_sql_literal(dmk_password)}")
        else:
            print("Database master key already exists - reusing it.")

        cert_freshly_created = not _certificate_exists(cursor)
        if cert_freshly_created:
            print(f"Creating TDE certificate '{CERT_NAME}'...")
            cursor.execute(
                f"CREATE CERTIFICATE {CERT_NAME} WITH SUBJECT = 'Project Management Tool TDE Certificate'"
            )
        else:
            print(f"TDE certificate '{CERT_NAME}' already exists - reusing it.")

        if cert_freshly_created:
            pvk_password = secrets.token_urlsafe(32)
            cert_file, pvk_file = _write_backup_bundle(dmk_password or "(master key already existed - not generated by this run)", pvk_password)
            cursor.execute(
                f"BACKUP CERTIFICATE {CERT_NAME} TO FILE = {_sql_literal(str(cert_file))} "
                f"WITH PRIVATE KEY (FILE = {_sql_literal(str(pvk_file))}, "
                f"ENCRYPTION BY PASSWORD = {_sql_literal(pvk_password)})"
            )
    except pyodbc.Error as exc:
        print(f"TDE setup skipped - this SQL Server edition/instance does not support it: {exc}")
        return
    finally:
        master_conn.close()

    db_conn = _connect(settings.db_name)
    try:
        cursor = db_conn.cursor()
        if _database_encryption_key_exists(cursor, settings.db_name):
            print(f"'{settings.db_name}' already has a database encryption key - leaving encryption state as-is.")
            return

        print(f"Creating database encryption key for '{settings.db_name}'...")
        cursor.execute(
            f"CREATE DATABASE ENCRYPTION KEY WITH ALGORITHM = AES_256 ENCRYPTION BY SERVER CERTIFICATE {CERT_NAME}"
        )
        print(f"Enabling encryption on '{settings.db_name}' (runs as a background scan - may take a while on a large database)...")
        cursor.execute(f"ALTER DATABASE [{settings.db_name}] SET ENCRYPTION ON")
        print(f"TDE enabled on '{settings.db_name}'.")
    except pyodbc.Error as exc:
        print(f"TDE setup skipped - this SQL Server edition/instance does not support it: {exc}")
    finally:
        db_conn.close()


if __name__ == "__main__":
    setup_tde()
