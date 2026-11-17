import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";

export const metadata: Metadata = {
  title: "JARVIS — AI Crypto Research Platform",
  description: "Just A Rather Very Intelligent System: autonomous AI-powered crypto research and trading platform connected to Binance.",
  keywords: ["crypto", "trading", "AI", "Binance", "research", "JARVIS"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-base)" }}>
          <Sidebar />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
            <TopBar />
            <main style={{ flex: 1, padding: "24px", overflowY: "auto" }}>
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
