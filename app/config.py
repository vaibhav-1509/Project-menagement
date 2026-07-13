import secrets
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore")

    # SQL Server connection - filled in from .env (see .env.example)
    db_server: str = "localhost"
    db_port: int = 1433
    db_name: str = "ProjectManagement"
    db_user: str = "sa"
    db_password: str = ""
    db_driver: str = "ODBC Driver 17 for SQL Server"

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480

    cors_origins_raw: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    def _connection_url(self, database: str) -> str:
        # quote_plus so passwords/usernames with @, :, / etc. don't break the URL.
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        driver = quote_plus(self.db_driver)
        # Encrypt=yes turns on TLS for the SQL Server connection itself (distinct
        # from the app's own HTTPS story) - ODBC Driver 17 defaults to no
        # encryption at all, so without this every query/password hash travels
        # the wire in plaintext. TrustServerCertificate=yes is paired with it
        # because a local/LAN SQL Server instance normally only has a
        # self-signed certificate, not one issued by a CA the client trusts.
        return (
            f"mssql+pyodbc://{user}:{password}@{self.db_server}:{self.db_port}/{database}"
            f"?driver={driver}&Encrypt=yes&TrustServerCertificate=yes"
        )

    @property
    def database_url(self) -> str:
        return self._connection_url(self.db_name)

    @property
    def master_database_url(self) -> str:
        """Connects to the 'master' system database - used only to create db_name if it doesn't exist yet."""
        return self._connection_url("master")


def _ensure_jwt_secret(settings: Settings) -> None:
    """Generates a JWT secret on first run if .env left it blank, and writes it
    back to .env so it's stable across restarts - a secret that changes on every
    restart would silently invalidate every issued token."""
    if settings.jwt_secret_key:
        return

    generated = secrets.token_urlsafe(64)
    settings.jwt_secret_key = generated

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    for i, line in enumerate(lines):
        if line.startswith("JWT_SECRET_KEY="):
            lines[i] = f"JWT_SECRET_KEY={generated}"
            break
    else:
        lines.append(f"JWT_SECRET_KEY={generated}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


settings = Settings()
_ensure_jwt_secret(settings)
