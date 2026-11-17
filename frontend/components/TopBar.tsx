"use client";
import { useEffect, useState } from "react";

export default function TopBar() {
  const [time, setTime] = useState("");
  const [health, setHealth] = useState<"ok" | "error" | "loading">("loading");

  useEffect(() => {
    const update = () => setTime(new Date().toUTCString().replace(" GMT", " UTC"));
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const r = await fetch(process.env.NEXT_PUBLIC_API_URL + "/health");
        setHealth(r.ok ? "ok" : "error");
      } catch {
        setHealth("error");
      }
    };
    checkHealth();
    const id = setInterval(checkHealth, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <header style={{
      height: 56,
      background: "var(--bg-surface)",
      borderBottom: "1px solid var(--border)",
      display: "flex",
      alignItems: "center",
      padding: "0 24px",
      gap: 20,
      flexShrink: 0,
    }}>
      <div style={{ flex: 1 }} />

      {/* Clock */}
      <div style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
        {time}
      </div>

      {/* API Status */}
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <div style={{
          width: 7, height: 7,
          borderRadius: "50%",
          background: health === "ok" ? "var(--accent-green)" : health === "error" ? "var(--accent-red)" : "#64748b",
          boxShadow: health === "ok" ? "0 0 8px rgba(16,185,129,0.6)" : "none",
          transition: "all 0.3s",
        }} />
        <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 500 }}>
          API {health === "loading" ? "…" : health === "ok" ? "LIVE" : "DOWN"}
        </span>
      </div>

      {/* Mode badge */}
      <div className="badge badge-yellow">
        📄 Paper
      </div>
    </header>
  );
}
