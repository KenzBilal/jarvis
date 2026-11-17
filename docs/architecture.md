# JARVIS — Architecture

The approved-by-spec design. Agent instructions live in `AGENTS.md`;
current status lives in `progress.md`.

## 1. Purpose

Autonomous crypto research + trading: discover opportunities by itself, research
them with independent AI agents, decide with a Chief Analyst, gate every idea
with a deterministic Risk Engine, ask the human via Telegram, execute only
approved trades, and monitor the portfolio — with a Next.js dashboard on top.
**NO TRADE is always a valid decision.**

## 2. Component diagram

```
                 ┌─────────────────────────────────────────────────────┐
                 │                Supabase PostgreSQL                 │
                 │        (source of truth, all persistent data)      │
                 └────────▲──────────────▲──────────────▲─────────────┘
                          │              │              │
        ┌─────────────────┴───┐   ┌──────┴───────┐  ┌───┴──────────────┐
        │  Redis (queues,     │   │  FastAPI     │  │  Workers (arq)   │
        │  cache, locks)      │──▶│  API + bot   │◀─┤  scanner /       │
        └─────────────────────┘   │  gateway     │  │  research /      │
                                  └──────┬───────┘  │  monitoring      │
                                         │          └───┬─────────────┘
   Telegram ◀── approvals ──▶  telegram bot             │
   Dashboard (Next.js/Vercel) ◀── REST ──┘              ▼
                                    ┌───────────────────────────────────┐
                                    │  Agent layer (structured JSON)    │
                                    │  Market Analyst │ News Intel      │
                                    │        └──▶ Chief Analyst ──┐     │
                                    └─────────────────────────────┼─────┘
                                                                  ▼
                     ┌──────────────────┐   pass/fail   ┌─────────────────┐
                     │  Risk Engine     │──────────────▶│ Execution Engine│
                     │  (deterministic, │   (only path  │ Spot / Futures  │
                     │   cannot be      │    to orders) │ (paper default) │
                     │   overridden)    │               └────────┬────────┘
                     └──────────────────┘                        ▼
                                                          Binance REST/WS
```

## 3. Opportunity lifecycle

1. **Scanner** discovers eligible Spot + USDⓈ-M Futures symbols dynamically.
2. **Market Analyst** and **News Intelligence** run independently, persist JSON + Markdown reports.
3. **Chief Analyst** cross-checks both, challenges conclusions, compares candidates — and may return **NO TRADE**.
4. A structured **proposal** is produced: entry, stop-loss, take-profit, risk/reward, evidence.
5. **Risk Engine** validates deterministically: staleness, daily loss limit, exposure limit, kill switch — fails closed.
6. Proposal goes to **Telegram** for explicit human approval.
7. **Execution Engine** revalidates price/balance/risk, then places an idempotent order with protective SL/TP (paper by default).
8. Positions, orders, balances, and portfolio risk are monitored; everything lands in **immutable audit records**.

## 4. Agents and their boundaries

| Component | Role | May access |
|---|---|---|
| Market Analyst | Structure, indicators, volume, volatility, trend, derivatives | Public market data, reports |
| News Intelligence | Collection, verification, sentiment, event classification | News sources, reports |
| Chief Analyst | Cross-checks reports, selects strongest candidate or NO TRADE | Both reports, risk settings (read) |
| Risk Engine | Deterministic validation, **cannot be overridden** | Proposals, limits, kill switch |
| Execution Engine | Spot/futures adapters, **only holder of trading credentials** | Binance trading API, orders/positions |

Agents communicate exclusively through **Pydantic-validated JSON contracts**
(`agents/contracts/`) and persist runs, reports, and messages.

## 5. Folder structure

```
Jarvis/
├── AGENTS.md                     # project-wide agent rules
├── README.md
├── .gitignore                    # protects .env and secrets
├── .env.example                  # names + placeholders only
├── docker-compose.yml            # redis (+ optional test postgres)   [Phase 0]
├── docs/
│   ├── progress.md               # living status/decision log
│   ├── architecture.md           # this file
│   └── setup/                    # how to obtain/store each credential
├── backend/
│   ├── pyproject.toml            # uv-managed, pinned deps            [Phase 0]
│   ├── alembic/                  # migrations                         [Phase 0]
│   ├── src/jarvis/
│   │   ├── config/               # Pydantic Settings (dev/test/prod)
│   │   ├── db/                   # SQLAlchemy async + models/
│   │   ├── core/                 # logging, errors, retry, rate limits, kill switch
│   │   ├── api/                  # FastAPI routers
│   │   ├── market/               # Binance client, scanner, indicators
│   │   ├── news/                 # collectors, verification, sentiment
│   │   ├── agents/               # analysts + contracts/
│   │   ├── risk/                 # deterministic engine
│   │   ├── execution/            # spot/futures adapters, paper broker
│   │   ├── telegram/             # bot + approval workflow
│   │   ├── storage/              # Markdown/JSON report writers
│   │   └── workers/              # arq queues: scan / research / monitor
│   └── tests/
├── frontend/                     # Next.js + TS + Tailwind
└── infra/docker/                 # Dockerfiles (api, worker, bot)
```

## 6. Data model (Supabase PostgreSQL)

UUID PKs, `timestamptz` UTC, JSONB for reports/flexible payloads, real FKs,
composite indexes on time-series keys, `created_at`/`updated_at` everywhere,
Alembic migrations from day one.

| Domain | Tables | Notes |
|---|---|---|
| Exchange | `exchange_accounts`, `trading_symbols`, `symbol_filters`, `timeframes` | unique `(account, symbol)`; filters JSONB |
| Market data | `candles`, `market_snapshots`, `indicators` | unique `(symbol, timeframe, open_time)`; **no raw ticks** |
| News | `news_sources`, `news_documents`, `news_events`, `news_mentions` | event↔document M2M; sentiment JSONB |
| Agents | `agent_runs`, `agent_tasks`, `agent_reports`, `agent_messages` | full run lineage, JSONB + Markdown |
| Proposals | `trade_candidates`, `trade_proposals`, `proposal_approvals` | versioned; approval bound to Telegram user ID |
| Risk | `risk_settings`, `risk_checks`, `risk_events` | check results immutable; settings change only via audit |
| Execution | `orders`, `fills`, `positions`, `execution_logs` | unique `client_order_id` (idempotency) + exchange order IDs |
| Portfolio | `balances`, `portfolio_snapshots` | per-account interval snapshots |
| System | `system_settings`, `system_events`, `audit_logs` | append-only; kill-switch state |

PostgreSQL = source of truth. Redis = temporary data, caches, queues only.

## 7. Safety rules

Paper trading default · no live orders without Telegram approval · separate
research/risk/execution permissions · revalidate price/balance/risk immediately
before execution · idempotent orders · protective SL/TP on every position ·
no withdrawal permission on API keys · daily loss limits, exposure limits,
global kill switch · stale-data rejection · immutable audit records ·
fail closed on service/feed failure · credentials never reach frontend or
research agents.

## 8. Configuration groups

| Group | Status | Needed at |
|---|---|---|
| A. GitHub | ✅ provided | repo + Vercel |
| B. Supabase | ✅ provided + verified | Phase 0 |
| C. Binance | deferred | Phase 2 (read-only), Phase 8 (testnet) |
| D. Telegram | deferred | Phase 6 |
| E. AI provider | deferred | Phase 2 |
| F. Redis / news / monitoring | local Redis, no creds | Phase 0 |
