import { fetchPositions, type Position } from "@/lib/api";
export default async function PositionsPage() {
  const positions = await fetchPositions();
  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Positions</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Open paper trading positions with real-time P&amp;L tracking</p>
      </div>
      <div className="card">
        {positions.length === 0 ? (
          <div style={{ color: "var(--text-muted)", padding: "40px 0", textAlign: "center" }}>No open positions. Approve a trade proposal via Telegram to open one.</div>
        ) : (
          <table className="data-table">
            <thead><tr><th>Symbol</th><th>Direction</th><th>Entry</th><th>SL</th><th>TP</th><th>Qty</th><th>Unrealized PnL</th><th>Opened</th></tr></thead>
            <tbody>
              {positions.map((p: Position) => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 700 }}>{p.symbol}</td>
                  <td><span className={`badge ${p.direction === "long" ? "badge-green" : "badge-red"}`}>{p.direction === "long" ? "▲ LONG" : "▼ SHORT"}</span></td>
                  <td style={{ fontFamily: "var(--font-jetbrains), ui-monospace, monospace" }}>${p.entry_price.toFixed(4)}</td>
                  <td style={{ color: "var(--accent-red)", fontFamily: "var(--font-jetbrains), ui-monospace, monospace" }}>${p.stop_loss.toFixed(4)}</td>
                  <td style={{ color: "var(--accent-green)", fontFamily: "var(--font-jetbrains), ui-monospace, monospace" }}>${p.take_profit.toFixed(4)}</td>
                  <td style={{ fontFamily: "var(--font-jetbrains), ui-monospace, monospace" }}>{p.quantity.toFixed(6)}</td>
                  <td style={{ color: p.unrealized_pnl >= 0 ? "var(--accent-green)" : "var(--accent-red)", fontFamily: "var(--font-jetbrains), ui-monospace, monospace", fontWeight: 600 }}>{p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toFixed(2)} USDT</td>
                  <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{new Date(p.opened_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
