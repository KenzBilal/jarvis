"""Settings validation: fail-closed behaviour, paper-only trading, secret hygiene."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from jarvis.config.settings import Settings

DB_URL = "postgresql://user:s3cr3t-pw@aws-0-eu.pooler.supabase.com:5432/postgres"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SUPABASE_DB_URL", "REDIS_URL", "JARVIS_ENV", "TRADING_MODE", "LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)


def make(**overrides: str) -> Settings:
    values: dict[str, str] = {"supabase_db_url": DB_URL, **overrides}
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_defaults_are_safe() -> None:
    s = make()
    assert s.trading_mode == "paper"
    assert s.jarvis_env == "development"
    assert s.live_trading_enabled is False
    assert s.redis_url.get_secret_value() == "redis://localhost:6379/0"


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_DB_URL", DB_URL)
    monkeypatch.setenv("REDIS_URL", "redis://example:6380/2")
    monkeypatch.setenv("JARVIS_ENV", "Test")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.jarvis_env == "test"
    assert s.redis_url.get_secret_value() == "redis://example:6380/2"


def test_loads_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"SUPABASE_DB_URL={DB_URL}\nJARVIS_ENV=test\n", encoding="utf-8")
    s = Settings(_env_file=env_file)  # type: ignore[call-arg]
    assert s.jarvis_env == "test"


def test_missing_database_url_fails_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("mode", ["live", "LIVE", "production", "", "paper-live", "true"])
def test_live_trading_is_impossible(mode: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make(trading_mode=mode)
    assert "paper" in str(excinfo.value)


def test_paper_mode_is_case_insensitive() -> None:
    assert make(trading_mode=" PAPER ").trading_mode == "paper"


def test_invalid_environment_rejected() -> None:
    with pytest.raises(ValidationError):
        make(jarvis_env="staging-ish")


@pytest.mark.parametrize(
    "url",
    ["mysql://u:p@h/db", "not a url", "postgresql://u:p@/db", "postgresql://u:p@host", ""],
)
def test_invalid_database_urls_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        make(supabase_db_url=url)


def test_invalid_redis_url_rejected() -> None:
    with pytest.raises(ValidationError):
        make(redis_url="http://localhost:6379")


@pytest.mark.parametrize(
    "scheme", ["postgresql", "postgres", "postgresql+asyncpg"]
)
def test_database_url_is_normalised_to_asyncpg(scheme: str) -> None:
    s = make(supabase_db_url=DB_URL.replace("postgresql", scheme, 1))
    assert s.database_url.startswith("postgresql+asyncpg://")


def test_sslmode_query_is_stripped_and_honoured() -> None:
    s = make(supabase_db_url=f"{DB_URL}?sslmode=require")
    assert "sslmode" not in s.database_url
    assert s.database_ssl is True
    assert make(supabase_db_url=f"{DB_URL}?sslmode=disable").database_ssl is False


def test_ssl_defaults_on_for_remote_off_for_local() -> None:
    assert make().database_ssl is True
    assert make(supabase_db_url="postgresql://u:p@localhost:5432/db").database_ssl is False


def test_production_requires_remote_database() -> None:
    with pytest.raises(ValidationError):
        make(jarvis_env="production", supabase_db_url="postgresql://u:p@localhost:5432/db")
    assert make(jarvis_env="production").is_production is True


def test_secrets_never_appear_in_repr_or_str() -> None:
    s = make(redis_url="redis://:redis-pw@cache.example:6379/0")
    text = f"{s!r} {s}"
    assert "s3cr3t-pw" not in text
    assert "redis-pw" not in text


def test_settings_are_immutable() -> None:
    s = make()
    with pytest.raises(ValidationError):
        s.trading_mode = "paper"  # type: ignore[misc]


def test_env_example_matches_settings_and_has_no_real_secrets() -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    names = {
        line.split("=", 1)[0].strip()
        for line in example.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {"SUPABASE_DB_URL", "REDIS_URL", "JARVIS_ENV", "TRADING_MODE"} <= names
    assert {n.lower() for n in names} <= set(Settings.model_fields)
    assert "TRADING_MODE=paper" in example.read_text(encoding="utf-8")
    assert "YOUR_DB_PASSWORD" in example.read_text(encoding="utf-8")
