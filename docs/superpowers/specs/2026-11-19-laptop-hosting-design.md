# JARVIS Laptop Self-Hosting — Always-On Bot & Pipeline

**Date:** 2026-11-19 · **Status:** awaiting owner approval · **Author:** brainstorming session (+ builder review, same day)

## Intent

The owner's laptop becomes JARVIS's always-on host. Power the laptop on and,
without touching anything:

1. all JARVIS services start automatically and survive sleep/wake and network
   drops;
2. the market scanner and research pipeline run on a schedule by themselves;
3. trade proposals arrive in the owner's Telegram with an Approve/Reject
   keyboard, valid for **5 minutes** — an unapproved proposal auto-expires
   (owner: "it should automatically be deleted");
4. only the owner's taps are accepted, and an approval drives a **paper**
   order through the deterministic Risk Engine;
5. open positions are **monitored and closed** on stop-loss/take-profit with
   real realized P&L (owner decision: basic version in this project).

Telegram is the operational interface. The web dashboard stays local-only
monitoring (owner decision 2026-11-19 — no public hosting, no tunnels).

## Why now

Phases 1–8 built and unit-tested every component (108/108 tests), but the
end-to-end path above has **never run once**. Verified gaps (grep/import/code
evidence, 2026-11-19):

| # | Gap | Evidence / status |
|---|-----|----------|
| 1 | `aiogram` not installed — bot code cannot import | `pyproject.toml` has no aiogram; `import aiogram` → `ModuleNotFoundError` |
| 2 | Nothing calls `start_polling()` — no process runs the bot | only definition in `telegram/bot.py:154`, zero callers |
| 3 | Nothing calls `send_proposal()` — proposals never reach Telegram | only definition in `telegram/bot.py:76`, zero callers |
| 4 | `run_research` is a stub ("stubbed until AI key added") — no analysis runs | `workers/research_worker.py:54-65` |
| 5 | No AI provider configured in `.env` | no `AI_PROVIDER`/key vars present — **resolved 2026-11-19:** owner provided Gemini + Groq keys; both verified live (model list + real completion → HTTP 200 each) |
| 6 | `TELEGRAM_APPROVED_USER_ID` unset → every tap answers "Unauthorized" | `bot.py:21,54` — **resolved 2026-11-19:** owner provided the ID; now in `.env` (kept out of the repo) |
| 7 | Nothing reads `ProposalApproval` — an approval writes a row and ends | grep: only `models.py` (schema) and `bot.py` (write) |
| 8 | Two competing `WorkerSettings`: the documented entry has only the heartbeat; the scanner cron lives in the other | `tasks.py:57-64` vs `research_worker.py:85-94` |
| 9 | Redis is not installed on this host (Arch Linux; `sudo` needs a password) → arq workers cannot start | `systemctl is-enabled redis` → not-found; no `redis-cli` |
| 10 | No auto-start of anything (no systemd units) | none exist in repo |
| 11 | **Scanner persists nothing** — it only logs counts, so there is no symbol pool to research | `research_worker.py:38-44` (reviewer-verified) |
| 12 | No writer for `risk_settings` rows, `PortfolioSnapshot`, or any P&L computation — `daily_pnl_pct` has no source; `PAPER_BALANCE_USDT` is a constant | reviewer-verified across `risk/`, `execution/`, `api/routes/data.py` |
| 13 | Nothing ever closes a position or updates `unrealized_pnl` — SL/TP stored but monitored by nobody | reviewer-verified |

## Goals

- **Boot → alive:** power on (even before GUI login) → services running;
  `Restart=always` covers crashes, sleep/wake, and network loss.
- **Self-running pipeline:** scanner persists symbols; research runs on a
  schedule with no manual trigger.
- **Proposals → Telegram → owner decision (within 5 min) → paper execution**,
  with the fail-closed invariants intact.
- **Living paper book:** positions close on SL/TP, realized P&L recorded, so
  the daily-loss check actually has data and can trigger.
- **Honest states everywhere:** unconfigured AI provider, down Redis, risk
  rejections, and expiries are all *visible* — in Telegram and `/ready` —
  never fake analysis, never a forced trade (NO TRADE is a valid decision).

## Non-goals / anti-goals

- No public exposure of the API: no tunnels, no port-forwarding (the API has
  no authentication; CORS binds browsers only).
- No live trading; paper only until Phase 9 (explicit owner approval, separate
  project).
- No dashboard deployment work (kept local; already decided).
- **No paid AI tiers in this project** — both providers run on their free
  tiers (verified limits in *AI providers* below); moving to paid is a
  later, deliberate owner decision. No gateway/router services (OpenRouter
  etc.) — direct provider calls only. Research still skips honestly if keys
  are ever removed — no fake output.
- No Binance keys in this project (paper trading uses public market data;
  testnet keys belong to Phase 8 activation — owner will provide them next).
- No advanced position features: no trailing stops, no partial fills, no
  manual close command (basic SL/TP close + realized P&L only).

## Constraints

- Stack fixed by `AGENTS.md`: FastAPI + arq/Redis + Supabase (cloud) +
  aiogram Telegram; secrets only in `.env` (mode 600, git-ignored), never
  printed anywhere.
- Architecture invariants: Risk Engine is deterministic Python and fails
  closed; no LLM may override it; only the Execution Engine reads trading
  credentials; every execution path writes immutable audit records;
  idempotent orders via stable `client_order_id`; revalidate price/balance/
  risk immediately before every execution.
- Linux host with systemd — **host is Arch Linux**; `sudo` requires a
  password (the plan hands the owner one sudo command to paste at the Redis
  step; fallback documented: sudo-less user-space Redis).
- Repo at a fixed path; Python 3.13 pinned via `uv`.
- Settings load `.env` **relative to the process working directory**
  (`env_file=("../.env", ".env")`) → services must set `WorkingDirectory`
  (backend dir) or the env file is silently missed.

## Decided (as the owner decided them)

- **Host:** this laptop, whenever it is on and online (2026-11-19).
- **Telegram token:** provided, stored as `TELEGRAM_BOT_TOKEN` in `.env`
  (done; never echoed again; owner may rotate via BotFather later).
- **Approvals:** only the owner (user ID in `.env`, provided 2026-11-19), via
  Approve/Reject inline buttons.
- **Position lifecycle:** **basic version in this project** — SL/TP monitoring,
  closes, realized P&L, audit (owner, 2026-11-19).
- **Proposal expiry:** **keep 5 minutes; auto-expire** — owner's reasoning:
  prices change fast after analysis, so the approval window must be short and
  a stale proposal must lapse on its own (an honest NO TRADE).
- **AI providers:** owner provided **Gemini + Groq** keys (2026-11-19), both
  stored in `.env` and verified live; integration in scope (see *AI
  providers*). Analysis must still skip honestly if keys are ever removed —
  no fake output.
- **Dashboard:** local-only, excluded from this project.

## AI providers (keys verified 2026-11-19)

**Evidence:** Gemini `v1beta/models` → HTTP 200 (50 models) and a real
chat completion via Google's OpenAI-compatible endpoint → HTTP 200
`JARVIS OK`. Groq `/openai/v1/models` → HTTP 200 and a real completion →
HTTP 200 `JARVIS OK`.

**What the keys give us (free tiers, Nov 2026):**

| | Gemini (AI Studio key) | Groq |
|---|---|---|
| Workhorse model | `gemini-3.5-flash-lite` — **15 RPM / 500 req/day** | `openai/gpt-oss-120b` — **30 RPM / 1,000 req/day / 200K tokens/day** |
| Strongest free option | `gemini-3.8-flash` — only **5 RPM / 20 req/day** | gpt-oss-120b (same model, 131K context, ~500 tok/s) |
| Limits are per | Google Cloud **project** (extra keys share quota); reset midnight Pacific | **organization**; cached tokens excluded |
| Cost notes | Free tier prompts may train Google's products (no secrets in prompts — none are). Prices double for 3.8 Flash Jan 1 2027 (paid only). 2.5 models wind down Dec 1 2026 → avoid | Llama models left free tier (enterprise-only). Paid: $0.15/$0.60 per 1M |
| Quirk | 429 on any of RPM/TPM/RPD even if others have room | gpt-oss burns hidden **reasoning tokens** (64 completion tokens for a 2-word reply) — needs max-token headroom; empty content must be treated as an error |

**Our workload** (≤6 research cycles/day × ≤5 symbols × ~3 calls ≈ ≤90
LLM calls/day) fits inside Gemini flash-lite's 500/day with ~5× headroom;
Groq's 1,000/day fallback is never expected to throttle us. No payment
needed.

**Integration (builder's calls):**
- Generalize `llm.py`'s existing OpenAI-compatible path into a small
  provider registry (raw httpx, no new SDK dependencies):
  `gemini` → `https://generativelanguage.googleapis.com/v1beta/openai/`,
  `groq` → `https://api.groq.com/openai/v1`. Existing openai/anthropic/
  ollama paths untouched — nothing clashes.
- `.env` (and `.env.example` with placeholders): `AI_PROVIDER=gemini`,
  `AI_MODEL=gemini-3.5-flash-lite`, `AI_PROVIDER_FALLBACK=groq`,
  `AI_MODEL_FALLBACK=openai/gpt-oss-120b`.
- **Retry ladder:** primary ×3 with backoff (existing `retry_async`) → on
  429/5xx/transport failure **or empty content** → one attempt on the
  fallback → honest `llm.fallback_used` structured log. Empty content raises
  `LLMError` (the gpt-oss reasoning quirk above).
- Model choices are env-only: power-up later = change `AI_MODEL` (e.g. to
  `gemini-3.8-flash` once billing is linked) — no code change.

## Design (builder's calls — marked where decided)

1. **Services (systemd, user-level units + `loginctl enable-lingering`)** so
   they start at boot without waiting for GUI login, run as the owner's user
   (access to repo, `.env`, `uv`):
   - `jarvis-api.service` — uvicorn on `127.0.0.1:8000` (local dashboard +
     browser TopBar).
   - `jarvis-worker.service` — arq worker; **reconcile the two settings
     classes into one** (heartbeat + scanner cron + research cron +
     approval-execution cron + position-monitor cron).
   - `jarvis-bot.service` — dedicated long-polling runner
     (`python -m jarvis.telegram.runner`); long polling needs no inbound
     ports, which suits a NAT'd laptop.
   - Redis: system `redis` package via pacman — **owner runs one prepared
     sudo command when the plan reaches that step** (fallback if declined:
     user-space Redis under `~/.local` with a user unit; the plan carries
     both).
   - All units: `Restart=always`, `After=network-online.target` +
     `Wants=network-online.target`, `WorkingDirectory` set so `../.env`
     resolves.
2. **Pipeline wiring (code):**
   - Add pinned `aiogram` to `pyproject.toml`.
   - **Scanner persists its scan** (gap 11) into the symbols table
     (`is_active` maintenance) so a symbol pool exists.
   - Implement `run_research` for real: market analyst → news intelligence →
     chief analyst → **persist `TradeProposal`** → `send_proposal`. If no AI
     provider is configured: log an honest skip and return
     `{"status": "skipped_no_provider"}` (no fake output).
   - **Approval → execution:** arq cron finds
     `ProposalApproval(approved)` with no execution → paper broker → Risk
     Engine revalidation (fails closed → recorded rejection, not a crash).
     Idempotency via the unique `proposal_id` constraint + guard (double-run
     must not double-fill).
   - `/start` handler replies with the caller's numeric user ID (diagnostics
     after any token/account change); approvals are active from first run,
     fail-closed for everyone else.
3. **Position lifecycle (basic — owner in-scope decision):**
   - Monitoring cron (every minute): open positions vs current public price →
     SL/TP touch → close through the execution path with immutable audit
     records + realized P&L written back.
   - Realized P&L becomes the source for the daily-loss check (gap 12's main
     consequence): `daily_loss_limit_pct` goes from inert to active as soon as
     the first close happens. Until then it evaluates against 0 — honest for
     a fresh book.
   - `unrealized_pnl` refreshed by the same monitoring cron (dashboard shows
     live numbers again).
4. **Proposal expiry (owner decision):** keep `expiry_seconds=300`;
   execution rejects expired proposals (already implemented). Add an expiry
   watcher: when a pending proposal lapses, the bot **edits the Telegram
   message to "⏰ EXPIRED — no trade"** so the owner sees the lapse instead
   of wondering. Expiry is a NO TRADE, recorded as such.
5. **Research schedule (builder's defaults, config-level, owner may adjust):**
   research cron every **4 hours** + at startup; symbols = **top 5 by 24h
   volume** from the persisted pool; **max one undecided proposal per
   symbol**, skip symbols with open positions (anti-spam); no quiet hours
   initially (owner can ask); chief analyst's own NO_TRADE verdicts pass
   through untouched.
6. **Telegram feedback (builder's calls, closes reviewer's "silent states"
   gap):**
   - Every execution outcome is sent back as a reply on the proposal message:
     `✅ FILLED`, `⛔ REJECTED by risk (<check>)`, or `⏰ EXPIRED`.
   - `/status` command: honest one-liner — AI provider configured?, Redis
     up?, worker heartbeat age, open positions count.
7. **Risk data policy (builder's calls):**
   - No `risk_settings` row → use the code defaults (matches the existing
     read API's "using defaults" behavior); a row, when present, wins.
   - Missing P&L data evaluates as 0 (fresh book has no losses) — not a
     silent pass: the check still runs and logs its inputs.
   - Kill switch for now: direct DB write by the owner (documented in
     progress.md); no write endpoint in this project (API stays read-only).
   - Execution additionally guards **entry-price drift**: fill is rejected
     if current price has moved beyond a small tolerance from the analyzed
     entry (bounds the 5-minute window's residual risk).
8. **Tests (builder's call):** new glue is covered by (a) unit tests in the
   existing mocked style — research-chain wiring with a fake LLM, unauthorized
   approve, expiry lapse, drift guard — and (b) integration tests against the
   **real Supabase** for the DB-dependent proofs (approved → position + audit
   rows, unique-constraint idempotency, SL/TP close), isolated with test
   prefixes and cleaned up, **auto-skipping when the test-DB env var is
   absent** so plain `pytest` stays green everywhere.

## Verification (acceptance)

- `uv run pytest` green (unit always; integration with test-DB env set);
  frontend lint/build untouched (no frontend changes expected).
- **Live E2E, part 1 (now):** after `reboot`, all services `active`; bot
  answers `/start` with the ID; a proposal **seeded by a clearly test-only
  helper** (not shipped as product code) arrives in Telegram → owner taps
  Approve → paper position + audit rows; a second tap / second user →
  "Unauthorized"; letting one lapse → message edits to EXPIRED; SL/TP touch →
  position closes with realized P&L and audit trail.
- **Live E2E, part 2:** a real research cycle with the configured Gemini
  primary → genuine proposal (or an honest chief-analyst NO TRADE —
  nondeterminism is honest) → Telegram → approve → paper position; plus one
  forced-fallback check proving the Groq path engages when the primary is
  rate-limited.
- `docs/progress.md` updated; `git status` clean of secrets.

## Open items

- **Binance API key + secret** (owner will provide next) — for Phase 8
  testnet activation only; not required by this project's acceptance.

## What's left to the builder

Everything in *Design* §1–8 plus tests, both live E2E runs, the one sudo
step handed to the owner, and the `docs/progress.md` update — planned out in
a separate implementation plan.
