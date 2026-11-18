import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "JARVIS — AI Crypto Research Platform",
    template: "%s · JARVIS",
  },
  description:
    "Just A Rather Very Intelligent System: autonomous AI-powered crypto research and trading platform connected to Binance.",
  keywords: ["crypto", "trading", "AI", "Binance", "research", "JARVIS"],
  // A trading dashboard should never be indexed
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#080c14",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable}`}>
      <body>
        <div className="app-shell">
          <Sidebar />
          <div className="app-body">
            <TopBar />
            <main id="main" className="app-main">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
