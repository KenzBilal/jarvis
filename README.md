# JARVIS

**J**ust **A** **R**ather **V**ery **I**ntelligent **S**ystem — an autonomous
AI-powered cryptocurrency research and trading platform connected to Binance.

JARVIS scans eligible Binance Spot and USDⓈ-M Futures markets, runs independent
AI research agents (Market Analyst, News Intelligence), lets a Chief Analyst
cross-check them into structured trade proposals, validates every proposal with
a deterministic Risk Engine, sends approved opportunities to Telegram, and
executes only what you explicitly approve — with paper trading as the default.

> **Status: pre-Phase 0 (scaffold only).** No application code yet.
> See [`docs/progress.md`](docs/progress.md) for current status and
> [`docs/architecture.md`](docs/architecture.md) for the design.

## Principles

- **NO TRADE is a valid decision.** Trades are never forced.
- **The Risk Engine is deterministic** and cannot be overridden by AI.
- **Fail closed** when critical services or data feeds fail.
- **Credentials never reach the frontend or research agents.**
- PostgreSQL is the source of truth; Redis holds only temporary data.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS → Vercel |
| Backend | Python 3.13, FastAPI, Pydantic, AsyncIO, SQLAlchemy, Alembic |
| Database | Supabase PostgreSQL |
| Cache / queues | Redis (`arq` workers) |
| Exchange | Binance REST + WebSocket |
| Notifications | Telegram Bot API |
| AI | Provider-independent (hosted APIs + optional Ollama) |
| DevOps | Docker Compose, GitHub |

## Repository layout

```
backend/    Python API, agents, risk engine, execution, workers
frontend/   Next.js dashboard
docs/       Architecture, progress log, setup guides
infra/      Docker configuration
```

## Security

Secrets live in `.env` (git-ignored, `chmod 600`); `.env.example` contains
placeholders only. Exchange API keys must be read-only and must never have
withdrawal permissions.
