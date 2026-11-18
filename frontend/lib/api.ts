export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ── Response contracts (mirror the FastAPI routes) ───────────────── */

export type Health = { status: string };
export type Ready = { status?: string; checks?: Record<string, string> };

export type SymbolRow = {
  id: string;
  symbol: string;
  market: string;
  last_price?: number | null;
  price_change_pct_24h?: number | null;
  volume_24h_usdt?: number | null;
  is_active?: boolean;
};

export type Proposal = {
  id: string;
  symbol: string;
  direction: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  risk_reward_ratio: number;
  confidence: number;
  created_at: string;
};

export type Position = {
  id: string;
  symbol: string;
  direction: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  quantity: number;
  unrealized_pnl: number;
  opened_at: string;
  is_open?: boolean;
};

export type AgentRun = {
  id: string;
  agent_type: string;
  status: string;
  correlation_id?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type Portfolio = { total_value_usdt?: number; daily_pnl?: number };

export type RiskSettings = {
  message?: string;
  daily_loss_limit_pct: number;
  max_exposure_per_symbol_pct: number;
  max_position_size_pct: number;
  min_risk_reward: number;
  max_data_age_seconds: number;
  kill_switch: boolean;
};

/* ── Fetching ─────────────────────────────────────────────────────── */

async function safeFetch<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url, { cache: "no-store" });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function fetchHealth(): Promise<Health> {
  return (await safeFetch<Health>(`${API}/health`)) ?? { status: "unknown" };
}

export async function fetchReady(): Promise<Ready> {
  // /ready answers 503 with a JSON body when degraded — that body is data, not an error.
  try {
    const r = await fetch(`${API}/ready`, { cache: "no-store" });
    if (r.ok || r.status === 503) {
      const body = (await r.json()) as Ready;
      if (body && typeof body.status === "string") return body;
    }
  } catch {
    /* unreachable — fall through to the "unknown" fallback below */
  }
  return { status: "unknown", checks: {} };
}

export async function fetchSymbols(market?: string): Promise<SymbolRow[]> {
  const qs = market ? `?market=${market}` : "";
  return (await safeFetch<SymbolRow[]>(`${API}/api/v1/symbols${qs}`)) ?? [];
}

export async function fetchProposals(): Promise<Proposal[]> {
  return (await safeFetch<Proposal[]>(`${API}/api/v1/proposals`)) ?? [];
}

export async function fetchPositions(openOnly = true): Promise<Position[]> {
  return (await safeFetch<Position[]>(`${API}/api/v1/positions?open_only=${openOnly}`)) ?? [];
}

export async function fetchAgentRuns(agentType?: string): Promise<AgentRun[]> {
  const qs = agentType ? `?agent_type=${agentType}` : "";
  return (await safeFetch<AgentRun[]>(`${API}/api/v1/agent-runs${qs}`)) ?? [];
}

export async function fetchPortfolio(): Promise<Portfolio | null> {
  return safeFetch<Portfolio>(`${API}/api/v1/portfolio/latest`);
}

export async function fetchRiskSettings(): Promise<RiskSettings | null> {
  return safeFetch<RiskSettings>(`${API}/api/v1/risk/settings`);
}
