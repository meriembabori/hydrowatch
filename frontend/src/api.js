const API_BASE = "http://localhost:8000";

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Erreur API (${res.status})`);
  }
  return res.json();
}

export const api = {
  getLakes: () => fetch(`${API_BASE}/lakes/`).then(handle),
  getIndicators: (lakeId = 1) =>
    fetch(`${API_BASE}/indicators/?lake_id=${lakeId}`).then(handle),
  compare: (lakeId, yearA, yearB) =>
    fetch(`${API_BASE}/comparisons/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lake_id: lakeId, year_a: yearA, year_b: yearB }),
    }).then(handle),
  getMlMetrics: () => fetch(`${API_BASE}/ml/metrics`).then(handle),
};
