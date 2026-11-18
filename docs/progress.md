# JARVIS Progress Log

## Current Status: Phases 0–10 implemented (testnet/live pending credentials)

---

## Phase 0 — Foundation ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/config/settings.py` — Pydantic Settings (fail-closed, paper-only, secret hygiene)
- `backend/src/jarvis/core/logging.py` — Structured JSON logging, correlation IDs, `CorrelationIdMiddleware`
- `backend/src/jarvis/core/errors.py` — Typed exceptions, `retry_async`, error envelopes
- `backend/src/jarvis/api/main.py` — FastAPI app factory, lifespan, middleware
- `backend/src/jarvis/api/routes/health.py` — `/health` + `/ready` with real DB/Redis probes
- `backend/src/jarvis/api/routes/data.py` — `/api/v1/` CRUD routes for all entities
- `backend/src/jarvis/db/base.py` — SQLAlchemy async engine, session factory, `Base`
- `backend/src/jarvis/workers/tasks.py` — arq worker heartbeat, paper-mode guard
- `backend/alembic/` — Async Alembic env, all migrations applied to Supabase
- `docker-compose.yml` — Redis + future services; Redis running natively (systemctl unavailable in env)

**Tests:** 49/49 pass

---

## Phase 1 — Market Scanner ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/market/binance_client.py` — Thin async Binance public REST client, rate-limit handling, retries
- `backend/src/jarvis/market/scanner.py` — Spot + Futures scanner, volume/blocklist/leveraged-token filtering
- `backend/src/jarvis/market/indicators.py` — Pure-Python TA: RSI, EMA, MACD, Bollinger Bands, ATR, `IndicatorBundle`
- `backend/src/jarvis/market/models.py` — `TradingSymbol`, `SymbolFilter`, `Candle`, `MarketSnapshot`, `IndicatorSnapshot`
- `backend/src/jarvis/workers/research_worker.py` — arq scanner job (every 30 min), research job stub

**Tests:** 19 new, all pass (68 total)

---

## Phase 2 — Market Analyst ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/agents/llm.py` — Provider-independent LLM adapter (OpenAI / Anthropic / Ollama)
- `backend/src/jarvis/agents/market_analyst.py` — Full agent: LLM analysis → `MarketReport` → persist; stub when AI not configured
- `backend/src/jarvis/agents/contracts.py` — Pydantic schemas for all inter-agent communication

**Decision:** `AI_PROVIDER` env var selects provider. Missing key → stub NO_TRADE report (never crashes).

---

## Phase 3 — News Intelligence ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/news/collector.py` — RSS collector (CoinDesk, CoinTelegraph, Bitcoin Magazine), LLM sentiment analysis, corroboration credibility scoring
- `backend/src/jarvis/news/models.py` — `NewsSource`, `NewsDocument`, `NewsEvent`, `NewsMention`

---

## Phase 4 — Agent Orchestration ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/agents/models.py` — `AgentRun`, `AgentTask`, `AgentReport`, `AgentMessage`
- `backend/src/jarvis/storage/report_writer.py` — Markdown + JSON report output to `agent_reports/`

---

## Phase 5 — Chief Analyst ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/agents/chief_analyst.py` — Cross-checks Market + News reports; enforces R:R ≥ 1.5, confidence ≥ 0.65; produces `TradeProposal` or NO_TRADE

---

## Phase 6 — Telegram ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/telegram/bot.py` — aiogram v3 bot; Approve/Reject inline keyboard; writes `ProposalApproval` to DB; stubs gracefully when `TELEGRAM_BOT_TOKEN` not set

**To activate:** Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_APPROVED_USER_ID` to `.env`

---

## Phase 7 — Risk Engine ✅ COMPLETE

**What was built:**
- `backend/src/jarvis/risk/engine.py` — Deterministic 6-check risk engine: kill switch, stale data, daily loss limit, symbol exposure, position size, R:R. Fails closed. No LLM interaction.
- `backend/src/jarvis/execution/models.py` — All execution/portfolio/audit models

**Tests:** 25 new risk engine tests, all pass (102 total)

---

## Phase 8 — Binance Testnet/Execution ✅ STRUCTURE COMPLETE

**What was built:**
- `backend/src/jarvis/execution/paper_broker.py` — Paper trade execution: re-validates risk before fill, writes `Order → Fill → Position` audit trail

**Pending:** Add `BINANCE_TESTNET_API_KEY` + `BINANCE_TESTNET_API_SECRET` to `.env` and implement signed REST client for real order placement.

---

## Phase 9 — Live Execution 🔒 LOCKED

Intentionally not implemented. Requires Phase 8 validation + explicit unlock decision.

---

## Phase 10 — Dashboard ✅ COMPLETE

**What was built:**
- `frontend/` — Next.js 16 + TypeScript + Tailwind dashboard
- Pages: Overview, Symbols, Proposals, Positions, Agent Runs, Risk Settings
- Real-time API health indicator, UTC clock, paper trading badge
- All pages connect to FastAPI via `lib/api.ts`

---

## Database

- Supabase PostgreSQL (ap-south-1 region)
- 30+ tables created via Alembic autogenerate migration `8b4d190739fd`
- Session pooler (port 5432) — direct connection unavailable (no IPv6 in this env)

## Infrastructure (Local Dev)

- Redis: system redis-server on port 6379 (Docker unavailable — iptables blocked)
- FastAPI: `uvicorn` on port 8000
- Next.js: dev server on port 3000

## Credentials Needed to Activate Remaining Features

| Feature | Variable |
|---------|----------|
| LLM analysis | `AI_PROVIDER` + provider key |
| Telegram approvals | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_APPROVED_USER_ID` |
| Binance testnet execution | `BINANCE_TESTNET_API_KEY` + `BINANCE_TESTNET_API_SECRET` |

---

## Test Summary

| Phase | Tests | Status |
|-------|-------|--------|
| 0 — Foundation | 49 | ✅ All pass |
| 1 — Market Scanner | 19 | ✅ All pass |
| 2–7 — Agents + Risk | 34 | ✅ All pass |
| CORS + settings (2026-11-18) | 6 | ✅ All pass |
| **Total** | **108** | ✅ **108/108** |

---

## Dashboard Redesign Integration — 2026-11-18 (commit `e722f8c`)

Owner supplied 3 redesigned frontend files (`globals.css`, `layout.tsx`, overview
`page.tsx`); integrated them and fixed everything they depended on.

**Applied (owner's files):**
- `app/globals.css` — responsive `.app-shell`/`.grid-stats`/`.grid-two`, soft color
  tokens, `@theme inline`, WCAG-safe `--text-muted`. Deliberately **removes** the old
  global `*{margin:0;padding:0}` reset in favour of Tailwind preflight.
- `app/layout.tsx` — `next/font/google` (Inter + JetBrains Mono → `--font-inter` /
  `--font-jetbrains`), metadata template, viewport themeColor, shell markup.
- `app/page.tsx` — degraded-data banner (`Promise.allSettled`), trading-mode labels
  (`NEXT_PUBLIC_TRADING_MODE`), system-health dots, phase roadmap with progress bar.

**Fixed (remaining issues found during review):**
1. **Tailwind was never wired** — `@tailwindcss/turbopack` was installed but absent
   from `next.config.ts`, so `@import "tailwindcss"` compiled to *nothing* (no
   preflight, no utilities, no `@theme`). Added the `turbopack.rules` loader;
   built CSS went 4.6 KB → 26.6 KB with preflight confirmed.
2. **20 hardcoded `'JetBrains Mono'` font stacks** across 7 files — `next/font`
   generates its own family names, so those never matched → replaced with
   `var(--font-jetbrains)`.
3. **Sidebar `minHeight:100vh`** overflowed the new `height:100dvh` shell and
   clipped its footer → `height:"100%"`.
4. **Risk page** used a fixed inline `1fr 1fr` grid → responsive `.grid-two`.
5. **10 lint errors** (`no-explicit-any`) → typed response contracts in
   `lib/api.ts` (`AgentRun`, `Position`, `Proposal`, `SymbolRow`, `RiskSettings`…).
6. `dump.rdb` (local Redis dump) added to `.gitignore`.

**Verification (fresh, before push):** `npm run lint` clean · `npm run build`
clean · all 6 routes return **200** via `next start` with no error markers ·
13 self-hosted woff2 font files emitted · backend `pytest` **102/102** ·
pushed `cd0c2f9..e722f8c`, `main` == `origin/main`, working tree clean.

---

## Strict Monochrome Theme + Status Honesty — 2026-11-18 (commits `c524a6b`, `796e603`)

Owner request: "make it fully dark theme b/w". Delivered as **zero hues
anywhere**, with semantics carried by contrast instead of color.

**Theme (`c524a6b`):**
- Token layer rewritten to a true-black base + white/grey ramp. Accent vars keep
  their **names** (`--accent-green` etc.) so all `var(--accent-*)` markup updated
  automatically; only values changed.
- Semantic states by contrast: OK = outlined chip · danger = **inverted**
  (white bg / black text) · pending = dashed border · P&L keeps `+/-` and `▲/▼`.
- `html { filter: grayscale(1) }` — guarantee that emoji, focus rings and native
  UI can never leak colour (emoji are text, they can't be tokenized).
- Silver logo mark, metallic silver gradient wordmark, white glows/progress/dots,
  `themeColor: #000000`. Favicon verified already monochrome (all 3 ICO frames:
  0 non-grayscale pixels).

**Fixes found while verifying (`796e603`):**
1. **Degraded banner was dead code** — `safeFetch` never rejects, so the
   rejection-based `failed` filter could never fire. Now derived from the
   readiness probe ("unknown" = API unreachable → all sources listed).
2. **Empty System Health card** — `/ready` answers **503 with a JSON body** when
   degraded, but `safeFetch` dropped non-2xx bodies; plus an empty `checks`
   object is truthy so the section rendered header-only. `fetchReady` now parses
   the 503 body; the section renders only with actual checks.
3. **No CORS on the API** — the browser-side TopBar `/health` poll was
   permanently `API DOWN` while the API was healthy (server-side fetches
   unaffected). Added explicit `CORS_ORIGINS` allow-list (settings + validator
   that **rejects wildcards**), middleware registered so correlation IDs stay
   outermost. `.env.example` documents adding the Vercel URL for prod.

**Verification (fresh, before push):**
- Source sweep: all **35** color literals grayscale (r=g=b) · built CSS: all
  **77** literals grayscale, `filter:grayscale()` present, preflight intact ·
  no Tailwind hue utilities in markup.
- Playwright pixel proof: screenshots of `/`, `/risk`, `/proposals` →
  **max saturation 0/255, 0 coloured pixels of 1.3M each** (emoji included) ·
  DOM computed-style scan: no non-grey color on any element.
- API-up state: System Health renders `Database: Ok / Redis: Unavailable` from
  the 503 body; TopBar dot measured as **solid white disc** + DOM text
  `API LIVE` (before CORS: `API DOWN`); API-down state shows the degraded
  banner and hides System Health.
- `npm run lint` clean · `npm run build` clean · backend `pytest` **108/108**
  (+6 CORS/settings tests) · pushed `db878e0..796e603`, `main` == `origin/main`,
  working tree clean.

## Vercel Deployment Wiring — 2026-11-18

**Goal:** the deployed frontend (`https://jarvisforme.vercel.app/`) must be able
to call the API (CORS) and the TopBar health poll must work in any build.

**State of the deployment (verified by fetching it):**
- Vercel serves **200** and runs the latest pushed code (post-fix degraded
  banner present in its HTML) — the monochrome theme is live.
- Its server-side fetches fail by design of the current topology: there is **no
  publicly reachable backend yet**, so the dashboard honestly shows the
  degraded banner + "—" values. `NEXT_PUBLIC_API_URL` is not set on Vercel.

**Changes:**
1. **CORS allow-list now includes the deployed origin** —
   `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://jarvisforme.vercel.app`
   in `.env.example` (committed) and the local `.env` (git-ignored, mode 600).
2. **TopBar now imports the shared `API` base from `lib/api.ts`** instead of
   reading `process.env.NEXT_PUBLIC_API_URL` directly. The direct read is not
   inlined in the deployed client bundle, so production fetched the relative
   URL `undefined/health` (always error). Both paths now resolve identically
   (env var, else `http://localhost:8000` fallback).

**Verification (fresh):**
- CORS end-to-end against a live uvicorn: simple GET from
  `https://jarvisforme.vercel.app` → `access-control-allow-origin` echoes the
  origin; preflight OPTIONS → grants `GET` + `content-type`; **control**: an
  unlisted origin gets **no** ACAO header (browser blocks it).
- Playwright runtime check of the TopBar change: DOM text `API LIVE` and the
  health dot measured as a **solid white disc** (center column grays
  246–255).
- Local full-stack render (`next start :3114` + backend): **no degraded
  banner**, all five API fetches 200 (DB reachable; tables empty — honest
  empty-state, portfolio shows "—" until snapshots exist).
- `npm run lint` clean · `npm run build` clean (7 routes) · backend `pytest`
  **108/108** · test servers stopped, ports 8000/3114 free.

**Remaining gap (needs a hosting decision):** a publicly hosted backend + set
`NEXT_PUBLIC_API_URL` in the Vercel project env to that backend's URL (and add
that backend's `CORS_ORIGINS` to include the Vercel origin). Until then the
deployed dashboard stays in degraded state by design.
