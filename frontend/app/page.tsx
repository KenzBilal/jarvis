import {
  fetchReady,
  fetchSymbols,
  fetchPositions,
  fetchAgentRuns,
  fetchPortfolio,
} from "@/lib/api";
import StatCard from "@/components/StatCard";
import RecentAgentRuns from "@/components/RecentAgentRuns";
import TopSymbols from "@/components/TopSymbols";

// Live dashboard: never serve a cached render.
export const dynamic = "force-dynamic";

// Set NEXT_PUBLIC_TRADING_MODE=testnet|live when Phase 8/9 ships so labels stay honest.
const TRADING_MODE = process.env.NEXT_PUBLIC_TRADING_MODE ?? "paper";
const MODE_LABEL: Record<string, { header: string; unit: string; trades: string }> = {
  paper:   { header: "Paper trading mode", unit: "Paper USDT", trades: "paper trades" },
  testnet: { header: "Binance testnet",    unit: "Testnet USDT", trades: "testnet trades" },
  live:    { header: "Live trading",       unit: "USDT",       trades: "live trades" },
};
const mode = MODE_LABEL[TRADING_MODE] ?? MODE_LABEL.paper;

type Position  = { is_open?: boolean };
type Portfolio = { total_value_usdt?: number; daily_pnl?: number };
type Ready     = { status?: string; checks?: Record<string, string> };

const DASH = "—";

function usd(n: number) {
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default async function OverviewPage() {
  const [ready, symbols, positions, runs, portfolio] = await Promise.allSettled([
    fetchReady(),
    fetchSymbols(),
    fetchPositions(true),
    fetchAgentRuns(),
    fetchPortfolio(),
  ]);

  const readyVal     = ready.status === "fulfilled" ? (ready.value as Ready) : null;
  const symbolList   = symbols.status === "fulfilled" ? symbols.value : null;
  const positionList = positions.status === "fulfilled" ? (positions.value as Position[]) : null;
  const runList      = runs.status === "fulfilled" ? runs.value : null;
  const port         = portfolio.status === "fulfilled" ? (portfolio.value as Portfolio) : null;
  const isLive       = readyVal?.status === "ready";

  // Which data sources failed → shown in a banner instead of silently rendering zeros
  const failed = [
    ["health",    ready],
    ["symbols",   symbols],
    ["positions", positions],
    ["agent runs", runs],
    ["portfolio", portfolio],
  ]
    .filter(([, r]) => (r as PromiseSettledResult<unknown>).status === "rejected")
    .map(([name]) => name as string);

  const hasPortfolioValue = typeof port?.total_value_usdt === "number";
  const hasPnl            = typeof port?.daily_pnl === "number";
  const dailyPnl          = port?.daily_pnl ?? 0;
  const openCount         = positionList ? positionList.filter((p) => p.is_open).length : null;

  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <header>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em" }}>
            <span className="gradient-text">JARVIS</span> Overview
          </h1>
          <div className={`badge ${isLive ? "badge-green" : "badge-red"}`} role="status">
            {isLive && <span className="live-dot" aria-hidden="true" style={{ width: 5, height: 5 }} />}
            {isLive ? "Systems Online" : "Offline"}
          </div>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
          AI-powered crypto research · {mode.header} · Real-time Binance data
        </p>
      </header>

      {/* Degraded-data banner */}
      {failed.length > 0 && (
        <div
          role="alert"
          className="card"
          style={{
            display: "flex", alignItems: "center", gap: 10,
            borderColor: "rgba(245,158,11,0.35)",
            background: "rgba(245,158,11,0.08)",
            padding: "12px 16px",
          }}
        >
          <span aria-hidden="true">⚠️</span>
          <span style={{ fontSize: 13, color: "var(--yellow-soft)" }}>
            Couldn&apos;t load: <strong>{failed.join(", ")}</strong>. Values shown as “{DASH}” are unavailable, not zero.
          </span>
        </div>
      )}

      {/* Stat row */}
      <section aria-label="Key metrics" className="grid-stats">
        <StatCard
          label="Portfolio Value"
          value={hasPortfolioValue ? usd(port!.total_value_usdt!) : DASH}
          sub={mode.unit}
          color="blue"
          icon="💰"
        />
        <StatCard
          label="Daily P&L"
          value={hasPnl ? `${dailyPnl >= 0 ? "+" : ""}${dailyPnl.toFixed(2)}%` : DASH}
          sub="vs yesterday"
          color={!hasPnl ? "blue" : dailyPnl >= 0 ? "green" : "red"}
          icon={!hasPnl || dailyPnl >= 0 ? "📈" : "📉"}
        />
        <StatCard
          label="Open Positions"
          value={openCount === null ? DASH : String(openCount)}
          sub={mode.trades}
          color="purple"
          icon="📊"
        />
        <StatCard
          label="Tracked Symbols"
          value={symbolList ? String(symbolList.length) : DASH}
          sub="USDT markets"
          color="yellow"
          icon="🔍"
        />
      </section>

      {/* System health */}
      {readyVal?.checks && (
        <section
          aria-label="System health"
          className="card"
          style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center", padding: "14px 20px" }}
        >
          <div style={{ fontWeight: 600, fontSize: 13, minWidth: 110 }}>System Health</div>
          {Object.entries(readyVal.checks).map(([key, val]) => {
            const ok = val === "ok";
            return (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <span className={`dot ${ok ? "dot-ok" : "dot-bad"}`} aria-hidden="true" />
                <span style={{ fontSize: 12, color: "var(--text-secondary)", textTransform: "capitalize" }}>
                  {key}:{" "}
                  <strong style={{ color: ok ? "var(--green-soft)" : "var(--red-soft)" }}>{String(val)}</strong>
                </span>
              </div>
            );
          })}
        </section>
      )}

      {/* Two-column */}
      <div className="grid-two">
        <TopSymbols symbols={(symbolList ?? []).slice(0, 8)} />
        <RecentAgentRuns runs={(runList ?? []).slice(0, 8)} />
      </div>

      <PhaseProgress />
    </div>
  );
}

/* ───────────── Roadmap ───────────── */

const PHASES = [
  { n: 0,  name: "Foundation",        done: true },
  { n: 1,  name: "Market Scanner",    done: true },
  { n: 2,  name: "Market Analyst",    done: true },
  { n: 3,  name: "News Intelligence", done: true },
  { n: 4,  name: "Orchestration",     done: true },
  { n: 5,  name: "Chief Analyst",     done: true },
  { n: 6,  name: "Telegram",          done: true },
  { n: 7,  name: "Risk Engine",       done: true },
  { n: 8,  name: "Binance Testnet",   done: false },
  { n: 9,  name: "Live Execution",    done: false },
  { n: 10, name: "Dashboard",         done: true },
] as const;

function PhaseProgress() {
  const done = PHASES.filter((p) => p.done).length;
  const pct  = Math.round((done / PHASES.length) * 100);

  return (
    <section aria-label="Phase progress" className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ fontWeight: 600, fontSize: 14 }}>Phase Progress</h2>
        <div className="badge badge-blue">{done}/{PHASES.length} phases</div>
      </div>

      <div
        className="progress-bar"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Roadmap completion"
        style={{ marginBottom: 16 }}
      >
        <div
          className="progress-fill"
          style={{ width: `${pct}%`, background: "linear-gradient(90deg, var(--accent-blue), var(--accent-cyan))" }}
        />
      </div>

      <ul style={{ display: "flex", gap: 6, flexWrap: "wrap", listStyle: "none" }}>
        {PHASES.map((p) => (
          <li
            key={p.n}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 500,
              border: "1px solid",
              borderColor: p.done ? "rgba(16,185,129,0.3)" : "var(--border)",
              background: p.done ? "rgba(16,185,129,0.1)" : "transparent",
              color: p.done ? "var(--green-soft)" : "var(--text-muted)",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span aria-hidden="true">{p.done ? "✓" : String(p.n)}</span>
            <span>{p.name}</span>
            <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
              {p.done ? " (complete)" : " (pending)"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
