import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function TimeSeriesChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <p className="text-slate-400 text-sm">
        Aucune donnée — lancez process_indices.py (Jour 2) pour ce lac.
      </p>
    );
  }

  return (
    <div className="w-full h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="year" stroke="#94a3b8" />
          <YAxis stroke="#94a3b8" label={{ value: "ha", angle: -90, position: "insideLeft", fill: "#94a3b8" }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", color: "#e2e8f0" }}
          />
          <Line type="monotone" dataKey="surface_ha" stroke="#38bdf8" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
