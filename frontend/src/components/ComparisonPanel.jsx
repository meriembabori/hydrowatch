import { useState } from "react";
import { api } from "../api";

export default function ComparisonPanel({ lakeId, availableYears }) {
  const [yearA, setYearA] = useState(availableYears?.[0] || "");
  const [yearB, setYearB] = useState(availableYears?.[availableYears.length - 1] || "");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleCompare = async () => {
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const data = await api.compare(lakeId, Number(yearA), Number(yearB));
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800 rounded-xl p-4 space-y-3">
      <h3 className="text-slate-200 font-semibold">Comparaison temporelle</h3>
      <div className="flex gap-3 items-center">
        <select
          value={yearA}
          onChange={(e) => setYearA(e.target.value)}
          className="bg-slate-700 text-slate-200 rounded px-2 py-1"
        >
          {availableYears?.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        <span className="text-slate-400">vs</span>
        <select
          value={yearB}
          onChange={(e) => setYearB(e.target.value)}
          className="bg-slate-700 text-slate-200 rounded px-2 py-1"
        >
          {availableYears?.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        <button
          onClick={handleCompare}
          disabled={loading}
          className="bg-sky-600 hover:bg-sky-500 text-white rounded px-3 py-1 disabled:opacity-50"
        >
          {loading ? "Calcul..." : "Comparer"}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {result && (
        <div className="grid grid-cols-2 gap-2 text-sm text-slate-300 pt-2">
          <div>Surface {result.year_a} : <span className="text-slate-100">{result.surface_a_ha} ha</span></div>
          <div>Surface {result.year_b} : <span className="text-slate-100">{result.surface_b_ha} ha</span></div>
          <div>Variation absolue : <span className="text-slate-100">{result.variation_absolute_ha} ha</span></div>
          <div>Variation relative : <span className="text-slate-100">{result.variation_relative_pct ?? "N/A"} %</span></div>
          <div className="text-emerald-400">Eau gagnée : {result.water_gained_ha} ha</div>
          <div className="text-red-400">Eau perdue : {result.water_lost_ha} ha</div>
        </div>
      )}
    </div>
  );
}
