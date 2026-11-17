# JARVIS - Phase 0 foundation

AI crypto research & trading platform. Phase 0 ships the backbone only: config, structured
logging, error handling, async DB/Redis plumbing, health endpoints, an arq worker and the
Alembic environment. **Trading is paper-only: `TRADING_MODE` accepts nothing else, and the
process refuses to start otherwise.**

Stack: Python 3.13, uv, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, arq + Redis,
httpx, structlog. Postgres is Supabase (session pooler); Docker Compose runs Redis only.

## Quickstart

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, a Supabase project.

```bash
# 1. Configure secrets (edit .env: set SUPABASE_DB_URL to your session-pooler string)
cp .env.example .env

# 2. Install dependencies (from the backend/ directory)
cd backend && uv sync

# 3. Start Redis (from the repo root)
docker compose up -d

# 4. Apply migrations (from backend/)
uv run alembic upgrade head

# 5. Run the API (from backend/) - then open http://127.0.0.1:8000/health
uv run uvicorn jarvis.api.main:app --reload

# 6. Run the tests (from backend/)
uv run pytest
```

Run the worker (optional, from `backend/`): `uv run arq jarvis.workers.tasks.WorkerSettings`

## Endpoints

| Path      | Purpose                                                             |
|-----------|---------------------------------------------------------------------|
| `/health` | Liveness - always 200 while the process is up; no dependencies.     |
| `/ready`  | Readiness - pings Postgres and Redis; **503** if either is down.    |

Every response carries an `X-Correlation-ID` header (a safe client-supplied id is reused),
and every log line is JSON that includes it. Errors share one envelope:
`{"error": {"code", "message", "correlation_id"}}`; unexpected failures return a generic 500.

## Configuration

All settings come from environment variables or `.env` (never commit it; `.gitignore` excludes `.env*`).

| Variable          | Notes                                                                        |
|-------------------|------------------------------------------------------------------------------|
| `SUPABASE_DB_URL` | Required. Session-pooler URL; `postgresql://` is converted to asyncpg. URL-encode special characters in the password. TLS is enforced for non-local hosts. |
| `REDIS_URL`       | Defaults to `redis://localhost:6379/0` (the Compose service).                |
| `JARVIS_ENV`      | `development` (default), `test`, `production`. Production hides `/docs` and rejects a local DB. |
| `TRADING_MODE`    | `paper` only. Any other value aborts startup.                                |
| `LOG_LEVEL`       | Optional: `DEBUG`..`CRITICAL`, default `INFO`.                               |

Secrets are held as `SecretStr` and masked in logs (including `user:password@` URLs).

## Layout

```
backend/src/jarvis/   config/ core/ db/ api/ workers/
backend/alembic/      async env.py (URL from Settings only); config lives in pyproject.toml
backend/tests/        run without Postgres or Redis (probes are faked)
```

Create a migration with `uv run alembic revision --autogenerate -m "message"` (from `backend/`).
