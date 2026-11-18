"use client";
export default function StatCard({ label, value, sub, color, icon }: { label: string; value: string; sub?: string; color: "blue" | "green" | "red" | "yellow" | "purple"; icon: string }) {
  const colors = { blue: "var(--accent-blue)", green: "var(--accent-green)", red: "var(--accent-red)", yellow: "var(--accent-yellow)", purple: "var(--accent-purple)" };
  // Monochrome: one neutral glow for every stat (accent hues are gone by design)
  const glow = "0 0 18px rgba(255,255,255,0.12)";
  return (
    <div className="card" style={{ position: "relative", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div className="stat-label">{label}</div>
          <div className="stat-value" style={{ color: colors[color], filter: `drop-shadow(${glow})`, marginTop: 8 }}>{value}</div>
          {sub && <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>{sub}</div>}
        </div>
        <div style={{ fontSize: 24, opacity: 0.7 }}>{icon}</div>
      </div>
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${colors[color]}, transparent)`, opacity: 0.4 }} />
    </div>
  );
}
