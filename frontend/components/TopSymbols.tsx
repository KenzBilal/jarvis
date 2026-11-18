"use client";
import type { SymbolRow } from "@/lib/api";

export default function TopSymbols({ symbols }: { symbols: SymbolRow[] }) {
  return (
    <div className="card">
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>Top Symbols by Volume</div>
      {symbols.length === 0 ? (
        <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "20px 0", textAlign: "center" }}>Run scanner to populate — no symbols yet</div>
      ) : (
        <table className="data-table">
          <thead><tr><th>Symbol</th><th>Market</th><th>24h Vol (USDT)</th><th>Change</th></tr></thead>
          <tbody>
            {symbols.map((s: SymbolRow) => {
              const chg = s.price_change_pct_24h ?? 0;
              return (
                <tr key={s.id}>
                  <td style={{ fontWeight: 600 }}>{s.symbol}</td>
                  <td><span className={`badge ${s.market === "spot" ? "badge-blue" : "badge-purple"}`}>{s.market}</span></td>
                  <td style={{ fontFamily: "var(--font-jetbrains), ui-monospace, monospace" }}>${(s.volume_24h_usdt ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                  <td style={{ color: chg >= 0 ? "var(--accent-green)" : "var(--accent-red)", fontFamily: "var(--font-jetbrains), ui-monospace, monospace" }}>{chg >= 0 ? "+" : ""}{chg.toFixed(2)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
