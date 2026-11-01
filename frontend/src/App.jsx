import { useEffect, useState } from "react";
import { api } from "./api";
import TimeSeriesChart from "./components/TimeSeriesChart";
import ComparisonPanel from "./components/ComparisonPanel";

export default function App() {
  const [lake, setLake] = useState(null);
  const [indicators, setIndicators] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .getLakes()
      .then((lakes) => setLake(lakes[0] || null))
      .catch((e) => setError(e.message));

    api
      .getIndicators(1)
      .then(setIndicators)
      .catch((e) => setError(e.message));
  }, []);

  const latest = indicators[indicators.length - 1];
  const years = indicators.map((i) => i.year);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-sky-400">HydroWatch</h1>
        <p className="text-slate-400 text-sm">
          {lake ? `${lake.name} — ${lake.region}` : "Chargement du lac..."}
        </p>
      </header>

      {error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded p-3 mb-4 text-sm">
          Erreur API : {error} — vérifiez que le backend tourne (uvicorn app.main:app --reload)
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-slate-800 rounded-xl p-4">
          <p className="text-slate-400 text-xs">Surface actuelle</p>
          <p className="text-2xl font-bold">{latest ? `${latest.surface_ha} ha` : "—"}</p>
        </div>
        <div className="bg-slate-800 rounded-xl p-4">
          <p className="text-slate-400 text-xs">Dernière année traitée</p>
          <p className="text-2xl font-bold">{latest ? latest.year : "—"}</p>
        </div>
        <div className="bg-slate-800 rounded-xl p-4">
          <p className="text-slate-400 text-xs">Couverture nuageuse (dernière image)</p>
          <p className="text-2xl font-bold">{latest ? `${latest.cloud_cover_pct}%` : "—"}</p>
        </div>
      </div>

      <div className="bg-slate-800 rounded-xl p-4 mb-6">
        <h2 className="text-slate-200 font-semibold mb-2">Évolution de la surface en eau</h2>
        <TimeSeriesChart data={indicators} />
      </div>

      {years.length >= 2 && <ComparisonPanel lakeId={1} availableYears={years} />}
    </div>
  );
}
