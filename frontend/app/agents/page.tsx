import { fetchAgentRuns, type AgentRun } from "@/lib/api";
export default async function AgentsPage() {
  const runs = await fetchAgentRuns();
  const statusColor = (s: string) => s === "success" ? "badge-green" : s === "failed" ? "badge-red" : s === "running" ? "badge-blue" : "badge-gray";
  const agentIcon = (t: string) => ({ market_analyst: "📊", news_intelligence: "📰", chief_analyst: "🧠", risk_engine: "🛡️", execution_engine: "⚡" })[t as string] ?? "🤖";
  const duration = (r: AgentRun) => {
    if (!r.started_at || !r.finished_at) return "—";
    const ms = new Date(r.finished_at).getTime() - new Date(r.started_at).getTime();
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  };
  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Agent Runs</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>History of all agent executions — market analysis, news, chief, risk</p>
      </div>
      <div className="card">
        <div style={{ marginBottom: 12 }}><span className="badge badge-blue">{runs.length} runs</span></div>
        {runs.length === 0 ? (
          <div style={{ color: "var(--text-muted)", padding: "40px 0", textAlign: "center" }}>No agent runs yet. Configure AI_PROVIDER in .env to enable agent execution.</div>
        ) : (
          <table className="data-table">
            <thead><tr><th>Agent</th><th>Status</th><th>Duration</th><th>Correlation ID</th><th>Created</th></tr></thead>
            <tbody>
              {runs.map((r: AgentRun) => (
                <tr key={r.id}>
                  <td><span style={{ marginRight: 6 }}>{agentIcon(r.agent_type)}</span>{r.agent_type.replace(/_/g, " ")}</td>
                  <td><span className={`badge ${statusColor(r.status)}`}>{r.status}</span></td>
                  <td style={{ fontFamily: "var(--font-jetbrains), ui-monospace, monospace", fontSize: 11 }}>{duration(r)}</td>
                  <td style={{ fontFamily: "var(--font-jetbrains), ui-monospace, monospace", fontSize: 10, color: "var(--text-muted)" }}>{r.correlation_id?.slice(0, 12) ?? "—"}</td>
                  <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{new Date(r.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
