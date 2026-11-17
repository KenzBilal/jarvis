import { fetchSymbols } from "@/lib/api";
export default async function SymbolsPage() {
  const symbols = await fetchSymbols();
  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Tracked Symbols</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>All USDT-denominated symbols meeting volume criteria</p>
      </div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
          <div className="badge badge-blue">{symbols.length} symbols</div>
        </div>
        {symbols.length === 0 ? (
          <div style={{ color: "var(--text-muted)", padding: "40px 0", textAlign: "center" }}>No symbols yet. The scanner job will populate this table automatically.</div>
        ) : (
          <table className="data-table">
            <thead><tr><th>Symbol</th><th>Market</th><th>Last Price</th><th>24h Change</th><th>Volume (USDT)</th><th>Status</th></tr></thead>
            <tbody>
              {symbols.map((s: any) => {
                const chg = s.price_change_pct_24h ?? 0;
                return (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 700 }}>{s.symbol}</td>
                    <td><span className={`badge ${s.market === "spot" ? "badge-blue" : "badge-purple"}`}>{s.market}</span></td>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>${(s.last_price ?? 0).toFixed(4)}</td>
                    <td style={{ color: chg >= 0 ? "var(--accent-green)" : "var(--accent-red)", fontFamily: "'JetBrains Mono', monospace" }}>{chg >= 0 ? "+" : ""}{chg.toFixed(2)}%</td>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>${(s.volume_24h_usdt ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                    <td><span className={`badge ${s.is_active ? "badge-green" : "badge-gray"}`}>{s.is_active ? "active" : "inactive"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
