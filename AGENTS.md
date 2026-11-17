# JARVIS — Agent Instructions

Shared, project-wide instructions for every coding agent working on JARVIS
(Just A Rather Very Intelligent System): an autonomous AI-powered crypto
research and trading platform connected to Binance.

**Read `docs/progress.md` before doing anything — it holds current status,
decisions, and blockers. Read `docs/architecture.md` for the design.**

## Stack (canonical — do not substitute)

- Frontend: Next.js + TypeScript + Tailwind, deployed on Vercel.
- Backend: Python 3.13 (pinned via `uv`), FastAPI, Pydantic, AsyncIO, SQLAlchemy 2.0 (async), Alembic.
- Database: **Supabase PostgreSQL — the only source of truth.**
- Cache/queues: Redis (temporary data, caches, task queues only).
- Workers: independent Python processes (`arq`).
- Notifications/approvals: Telegram Bot API.
- Exchange: Binance REST + WebSocket (in-house thin client on `httpx`).
- AI: provider-independent LLM protocol (hosted APIs + optional Ollama).
- Containers: Docker + Docker Compose.
- Reports: Markdown (human) + JSON (structured) in `agent_reports`.

**Forbidden:** Convex, a second primary database, a vector database, hardcoded
credentials, fake production functionality, unexplained placeholders that look
like finished features.

## Architecture invariants (non-negotiable)

1. **Paper trading is the default.** No live order without explicit Telegram approval.
2. **The Risk Engine is deterministic Python.** No LLM may override, soften, or bypass it. It fails closed.
3. **NO TRADE is a valid decision.** Never force a trade to produce activity.
4. **Only the Execution Engine reads trading credentials.** Research agents, the Chief Analyst, and the frontend never see them.
5. **Frontend talks only to FastAPI** — never to Supabase, Binance, or Redis directly.
6. **Revalidate** market price, balance, and risk immediately before every execution.
7. **Idempotent orders** via stable `client_order_id`; every execution path writes immutable audit records.
8. **Reject stale market data and invalid proposals.**
9. Binance API keys: read-only until Phase 8; **never** withdrawal permission.

## Secrets

- All secrets live in `.env` (mode `600`, git-ignored). `.env.example` holds names/placeholders only.
- Never print secret values in logs, errors, docs, reports, or chat responses.
- Never write credentials into Markdown, agent reports, or frontend env vars.
- Validate connections without displaying secrets.

## Coding standards

- Type hints everywhere; validate all external input with Pydantic.
- Async I/O for network, DB, and queue operations.
- Centralized error handling + structured logging (JSON) with request/run correlation IDs.
- Retries with exponential backoff; explicit Binance rate-limit handling.
- Unit + integration tests for risk, execution, and contracts (`backend/tests/`).
- Every major module gets a README or module docstring explaining its role.
- No secrets, no dead code, no TODOs masquerading as features.

## Agent communication contract

Agents exchange **structured JSON validated by Pydantic models** only
(`backend/src/jarvis/agents/contracts/`). Every run persists to
`agent_runs`, every report to `agent_reports` (JSONB + Markdown file), and
inter-agent messages to `agent_messages`.

## Project phases

| Phase | Scope |
|---|---|
| 0 | Foundation: config, Docker, Supabase, Redis, migrations, logging, health checks |
| 1 | Binance public market scanner + dynamic symbol discovery |
| 2 | Market Analyst |
| 3 | News Intelligence |
| 4 | Agent orchestration + research storage |
| 5 | Chief Analyst + trade proposals |
| 6 | Telegram integration + approval workflow |
| 7 | Risk engine + paper trading |
| 8 | Binance testnet/demo execution |
| 9 | Restricted live execution (after validation) |
| 10 | Next.js dashboard + production monitoring |

**Complete and verify each phase before starting the next.** Do not build
ahead across phases.

## Definition of done for any task

1. Tests pass (or are added and pass).
2. No secrets printed or committed (`git status` checked).
3. `docs/progress.md` updated with what changed, decisions made, and what's next.
4. Nothing claims to work unless it was actually run and verified.
