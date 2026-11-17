const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function safeFetch(url: string): Promise<any> {
  try {
    const r = await fetch(url, { cache: "no-store" });
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
}

export async function fetchHealth() {
  return safeFetch(`${API}/health`) ?? { status: "unknown" };
}

export async function fetchReady() {
  return safeFetch(`${API}/ready`) ?? { status: "unknown", checks: {} };
}

export async function fetchSymbols(market?: string) {
  const qs = market ? `?market=${market}` : "";
  return (await safeFetch(`${API}/api/v1/symbols${qs}`)) ?? [];
}

export async function fetchProposals() {
  return (await safeFetch(`${API}/api/v1/proposals`)) ?? [];
}

export async function fetchPositions(openOnly = true) {
  return (await safeFetch(`${API}/api/v1/positions?open_only=${openOnly}`)) ?? [];
}

export async function fetchAgentRuns(agentType?: string) {
  const qs = agentType ? `?agent_type=${agentType}` : "";
  return (await safeFetch(`${API}/api/v1/agent-runs${qs}`)) ?? [];
}

export async function fetchPortfolio() {
  return safeFetch(`${API}/api/v1/portfolio/latest`);
}

export async function fetchRiskSettings() {
  return safeFetch(`${API}/api/v1/risk/settings`);
}
