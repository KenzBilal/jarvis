"""Application settings (Pydantic Settings, loaded from the environment / ``.env``).

Security properties:
* Secrets are :class:`~pydantic.SecretStr` - they never appear in ``repr``/logs.
* ``TRADING_MODE`` only accepts ``paper``. Any other value (including ``live``) makes
  the process refuse to start, so live trading is impossible in this phase.
* Any invalid or missing required setting raises at startup (fail closed).
"""

from functools import lru_cache
from typing import Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

Environment = Literal["development", "test", "production"]
TradingMode = Literal["paper"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_ACCEPTED_DB_DRIVERS = frozenset({"postgresql", "postgres", "postgresql+asyncpg"})
_ACCEPTED_REDIS_SCHEMES = ("redis://", "rediss://")
_SSL_DISABLED_MODES = frozenset({"disable", "allow"})


class Settings(BaseSettings):
    """Typed, validated configuration. Field names map 1:1 to upper-case env vars."""

    model_config = SettingsConfigDict(
        # Later files override earlier ones: ../.env (repo root) < .env (cwd).
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )

    supabase_db_url: SecretStr = Field(
        description="Supabase Postgres connection string (session pooler).",
    )
    redis_url: SecretStr = Field(
        default=SecretStr("redis://localhost:6379/0"),
        description="Redis connection string used by arq and readiness checks.",
    )
    jarvis_env: Environment = "development"
    trading_mode: TradingMode = "paper"
    log_level: LogLevel = "INFO"

    # -- validators ---------------------------------------------------------- #
    @field_validator("trading_mode", mode="before")
    @classmethod
    def _paper_only(cls, value: Any) -> Any:
        normalized = value.strip().lower() if isinstance(value, str) else value
        if normalized != "paper":
            # Deliberately never echo the offending value.
            raise ValueError("TRADING_MODE must be 'paper': live trading is not available in this phase")
        return normalized

    @field_validator("jarvis_env", "log_level", mode="before")
    @classmethod
    def _normalize_case(cls, value: Any, info: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value.upper() if info.field_name == "log_level" else value.lower()

    @field_validator("supabase_db_url", mode="after")
    @classmethod
    def _validate_db_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip()
        try:
            url = make_url(raw)
        except ArgumentError:
            raise ValueError("SUPABASE_DB_URL is not a valid database URL") from None
        if url.drivername not in _ACCEPTED_DB_DRIVERS:
            raise ValueError("SUPABASE_DB_URL must be a postgresql:// URL")
        if not url.host or not url.database:
            raise ValueError("SUPABASE_DB_URL must include a host and a database name")
        return SecretStr(raw)

    @field_validator("redis_url", mode="after")
    @classmethod
    def _validate_redis_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip()
        if not raw.startswith(_ACCEPTED_REDIS_SCHEMES):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return SecretStr(raw)

    @model_validator(mode="after")
    def _production_requires_remote_database(self) -> Self:
        if self.jarvis_env == "production" and self._parsed_db_url().host in _LOCAL_HOSTS:
            raise ValueError("production requires a non-local SUPABASE_DB_URL")
        return self

    # -- derived values ------------------------------------------------------ #
    def _parsed_db_url(self) -> URL:
        return make_url(self.supabase_db_url.get_secret_value())

    @property
    def database_url(self) -> str:
        """SQLAlchemy async URL (``postgresql+asyncpg://``) without libpq-only query args."""
        url = self._parsed_db_url().set(drivername="postgresql+asyncpg")
        query = {k: v for k, v in url.query.items() if k != "sslmode"}
        return url.set(query=query).render_as_string(hide_password=False)

    @property
    def database_ssl(self) -> bool:
        """TLS is on for every non-local host unless ``?sslmode=disable`` is explicit."""
        url = self._parsed_db_url()
        mode = url.query.get("sslmode")
        if isinstance(mode, str):
            return mode.lower() not in _SSL_DISABLED_MODES
        return url.host not in _LOCAL_HOSTS

    @property
    def is_production(self) -> bool:
        return self.jarvis_env == "production"

    @property
    def live_trading_enabled(self) -> bool:
        """Always ``False`` in Phase 0. Exists so future code has one gate to check."""
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, validated once. Raises ``ValidationError`` if invalid."""
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
