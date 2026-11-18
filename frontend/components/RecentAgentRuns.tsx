"use client";
import type { AgentRun } from "@/lib/api";

export default function RecentAgentRuns({ runs }: { runs: AgentRun[] }) {
  const statusColor = (s: string) => s === "success" ? "badge-green" : s === "failed" ? "badge-red" : s === "running" ? "badge-blue" : "badge-gray";
  const agentIcon = (t: string) => t === "market_analyst" ? "📊" : t === "news_intelligence" ? "📰" : t === "chief_analyst" ? "🧠" : t === "risk_engine" ? "🛡️" : "🤖";
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>Recent Agent Runs</div>
      {runs.length === 0 ? (
        <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "20px 0", textAlign: "center" }}>No runs yet — configure AI_PROVIDER to start</div>
      ) : (
        <table className="data-table">
          <thead><tr><th>Agent</th><th>Status</th><th>Time</th></tr></thead>
          <tbody>
            {runs.map((r: AgentRun) => (
              <tr key={r.id}>
                <td><span style={{ marginRight: 6 }}>{agentIcon(r.agent_type)}</span>{r.agent_type.replace(/_/g, " ")}</td>
                <td><span className={`badge ${statusColor(r.status)}`}>{r.status}</span></td>
                <td style={{ fontFamily: "var(--font-jetbrains), ui-monospace, monospace", fontSize: 11 }}>{r.created_at ? new Date(r.created_at).toLocaleTimeString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
