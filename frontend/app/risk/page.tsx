import { fetchRiskSettings } from "@/lib/api";
export default async function RiskPage() {
  const settings = await fetchRiskSettings();
  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Risk Settings</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Deterministic risk engine parameters — LLM cannot override these</p>
      </div>
      {!settings || settings.message ? (
        <div className="card" style={{ color: "var(--text-muted)", padding: "40px 0", textAlign: "center" }}>No risk settings configured yet. Default values will apply when risk engine runs.</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <RiskMetric label="Daily Loss Limit" value={`${settings.daily_loss_limit_pct}%`} desc="Max portfolio loss per day" safe={!settings.kill_switch} />
          <RiskMetric label="Max Symbol Exposure" value={`${settings.max_exposure_per_symbol_pct}%`} desc="Max portfolio % per symbol" safe={true} />
          <RiskMetric label="Max Position Size" value={`${settings.max_position_size_pct}%`} desc="Max trade size per position" safe={true} />
          <RiskMetric label="Min Risk/Reward" value={`${settings.min_risk_reward}x`} desc="Minimum R:R to approve" safe={true} />
          <RiskMetric label="Max Data Age" value={`${settings.max_data_age_seconds}s`} desc="Reject stale market data after" safe={true} />
          <RiskMetric label="Kill Switch" value={settings.kill_switch ? "ACTIVE" : "Off"} desc="Global trading halt" safe={!settings.kill_switch} danger={settings.kill_switch} />
        </div>
      )}
      <div className="card" style={{ borderColor: "rgba(239,68,68,0.3)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div style={{ fontSize: 20 }}>🛡️</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Risk Engine Guarantees</div>
            <div style={{ color: "var(--text-secondary)", fontSize: 12, lineHeight: 1.8 }}>
              The risk engine is <strong>deterministic Python</strong> — no LLM can override, soften, or bypass it.<br/>
              It <strong>fails closed</strong>: any unexpected error produces a FAIL verdict.<br/>
              All risk check results are written as <strong>immutable audit records</strong>.<br/>
              <strong>NO TRADE is always a valid output.</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
function RiskMetric({ label, value, desc, safe, danger }: { label: string; value: string; desc: string; safe: boolean; danger?: boolean }) {
  return (
    <div className="card" style={{ borderColor: danger ? "rgba(239,68,68,0.4)" : undefined }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div className="stat-label">{label}</div>
          <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6, color: danger ? "var(--accent-red)" : safe ? "var(--accent-green)" : "var(--text-primary)" }}>{value}</div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>{desc}</div>
        </div>
        <div style={{ fontSize: 20 }}>{danger ? "🔴" : safe ? "✅" : "⚠️"}</div>
      </div>
    </div>
  );
}
