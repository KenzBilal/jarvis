import { fetchHealth, fetchReady, fetchSymbols, fetchPositions, fetchAgentRuns, fetchPortfolio } from "@/lib/api";
import StatCard from "@/components/StatCard";
import RecentAgentRuns from "@/components/RecentAgentRuns";
import TopSymbols from "@/components/TopSymbols";


export default async function OverviewPage() {
  const [health, ready, symbols, positions, runs, portfolio] = await Promise.allSettled([
    fetchHealth(),
    fetchReady(),
    fetchSymbols(),
    fetchPositions(true),
    fetchAgentRuns(),
    fetchPortfolio(),
  ]);

  const symbolList  = symbols.status  === "fulfilled" ? symbols.value  : [];
  const positionList= positions.status === "fulfilled" ? positions.value : [];
  const runList     = runs.status     === "fulfilled" ? runs.value     : [];
  const port        = portfolio.status === "fulfilled" ? portfolio.value : null;
  const isLive      = ready.status    === "fulfilled" && ready.value?.status === "ready";

  const openCount   = positionList.filter((p: any) => p.is_open).length;
  const totalValue  = port?.total_value_usdt ?? 0;
  const dailyPnl    = port?.daily_pnl ?? 0;

  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em" }}>
            <span className="gradient-text">JARVIS</span> Overview
          </h1>
          <div className={`badge ${isLive ? "badge-green" : "badge-red"}`}>
            <span className={isLive ? "live-dot" : ""} style={{ width: 5, height: 5 }} />
            {isLive ? "Systems Online" : "Offline"}
          </div>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
          AI-powered crypto research · Paper trading mode · Real-time Binance data
        </p>
      </div>

      {/* Stat row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard
          label="Portfolio Value"
          value={totalValue > 0 ? `$${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "$10,000.00"}
          sub="Paper USDT"
          color="blue"
          icon="💰"
        />
        <StatCard
          label="Daily P&L"
          value={`${dailyPnl >= 0 ? "+" : ""}${dailyPnl.toFixed(2)}%`}
          sub="vs yesterday"
          color={dailyPnl >= 0 ? "green" : "red"}
          icon={dailyPnl >= 0 ? "📈" : "📉"}
        />
        <StatCard
          label="Open Positions"
          value={String(openCount)}
          sub="paper trades"
          color="purple"
          icon="📊"
        />
        <StatCard
          label="Tracked Symbols"
          value={String(symbolList.length)}
          sub="USDT markets"
          color="yellow"
          icon="🔍"
        />
      </div>

      {/* System health */}
      {ready.status === "fulfilled" && (
        <div className="card" style={{ display: "flex", gap: 24 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-primary)", minWidth: 120 }}>
            System Health
          </div>
          {Object.entries((ready.value as any)?.checks ?? {}).map(([key, val]) => (
            <div key={key} style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <div style={{
                width: 7, height: 7, borderRadius: "50%",
                background: val === "ok" ? "var(--accent-green)" : "var(--accent-red)",
                boxShadow: val === "ok" ? "0 0 8px rgba(16,185,129,0.5)" : "none",
              }} />
              <span style={{ fontSize: 12, color: "var(--text-secondary)", textTransform: "capitalize" }}>
                {key}: <strong style={{ color: val === "ok" ? "var(--accent-green)" : "var(--accent-red)" }}>{String(val)}</strong>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Two-column */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <TopSymbols symbols={symbolList.slice(0, 8)} />
        <RecentAgentRuns runs={runList.slice(0, 8)} />
      </div>

      {/* Phase progress */}
      <PhaseProgress />
    </div>
  );
}

function PhaseProgress() {
  const phases = [
    { n: 0, name: "Foundation",          done: true },
    { n: 1, name: "Market Scanner",      done: true },
    { n: 2, name: "Market Analyst",      done: true },
    { n: 3, name: "News Intelligence",   done: true },
    { n: 4, name: "Orchestration",       done: true },
    { n: 5, name: "Chief Analyst",       done: true },
    { n: 6, name: "Telegram",            done: true },
    { n: 7, name: "Risk Engine",         done: true },
    { n: 8, name: "Binance Testnet",     done: false },
    { n: 9, name: "Live Execution",      done: false },
    { n: 10, name: "Dashboard",          done: true },
  ];

  const done = phases.filter(p => p.done).length;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>Phase Progress</div>
        <div className="badge badge-blue">{done}/{phases.length} phases</div>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {phases.map(p => (
          <div key={p.n} style={{
            padding: "6px 12px",
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 500,
            border: "1px solid",
            borderColor: p.done ? "rgba(16,185,129,0.3)" : "var(--border)",
            background: p.done ? "rgba(16,185,129,0.1)" : "transparent",
            color: p.done ? "#34d399" : "var(--text-muted)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}>
            <span>{p.done ? "✓" : String(p.n)}</span>
            {p.name}
          </div>
        ))}
      </div>
    </div>
  );
}
