"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",           icon: "⚡", label: "Overview" },
  { href: "/symbols",    icon: "🔍", label: "Symbols" },
  { href: "/proposals",  icon: "📋", label: "Proposals" },
  { href: "/positions",  icon: "📊", label: "Positions" },
  { href: "/agents",     icon: "🤖", label: "Agent Runs" },
  { href: "/risk",       icon: "🛡️",  label: "Risk Settings" },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside style={{
      width: 220,
      minHeight: "100vh",
      background: "var(--bg-surface)",
      borderRight: "1px solid var(--border)",
      display: "flex",
      flexDirection: "column",
      padding: "20px 12px",
      gap: 4,
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: "8px 14px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32,
            background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
            borderRadius: 8,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16,
          }}>J</div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 15, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>JARVIS</div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Research Platform</div>
          </div>
        </div>
      </div>

      {/* Nav items */}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV.map(({ href, icon, label }) => (
          <Link
            key={href}
            href={href}
            className={`nav-item ${path === href ? "active" : ""}`}
          >
            <span style={{ fontSize: 16 }}>{icon}</span>
            {label}
          </Link>
        ))}
      </div>

      {/* Footer */}
      <div style={{ marginTop: "auto", padding: "14px", borderTop: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="live-dot" />
          <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 500 }}>Paper Trading</span>
        </div>
        <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>v0.1.0 · Phase 0</div>
      </div>
    </aside>
  );
}
