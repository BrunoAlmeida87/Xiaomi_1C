import { useEffect, useState } from "react";
import { api } from "../api";

interface Session { id: number; start_ts: number; end_ts: number | null; simulated: boolean; area_m2: number | null; duration_min: number | null; start_battery: number | null; end_battery: number | null; result: string | null }
interface Snap { ts: number; battery: number | null; status: number | null }

function BatteryChart({ data }: { data: Snap[] }) {
  if (data.length < 2) return <p className="small muted">Dados insuficientes para o gráfico.</p>;
  const w = 800, h = 160, t0 = data[0].ts, t1 = data[data.length - 1].ts || t0 + 1;
  const pts = data.filter((d) => d.battery != null).map((d) => `${((d.ts - t0) / (t1 - t0 || 1)) * w},${h - ((d.battery ?? 0) / 100) * h}`);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart" role="img" aria-label="Bateria ao longo do tempo">
      {[25, 50, 75].map((y) => <line key={y} x1={0} x2={w} y1={h - (y / 100) * h} y2={h - (y / 100) * h} className="gridline" />)}
      <polyline points={pts.join(" ")} fill="none" stroke="var(--accent)" strokeWidth={2} />
    </svg>
  );
}

export function HistoryView({ simulated }: { simulated: boolean }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [snaps, setSnaps] = useState<Snap[]>([]);
  useEffect(() => {
    api.get<Session[]>("/api/history/sessions").then(setSessions);
    api.get<Snap[]>(`/api/history/snapshots?since=${Date.now() / 1000 - 86400}`).then(setSnaps);
  }, []);
  const real = sessions.filter((s) => s.simulated === simulated);
  const total = real.reduce((a, s) => a + (s.area_m2 ?? 0), 0);
  return (
    <div className="stack">
      <div className="card">
        <h2>Bateria — últimas 24 h {simulated && <span className="badge sim">SIMULADO</span>}</h2>
        <BatteryChart data={snaps} />
      </div>
      <div className="card">
        <h2>Sessões de limpeza registradas por este app</h2>
        <p className="small muted">Derivadas localmente das mudanças de estado (o histórico interno do robô não é exposto pelo protocolo local). {real.length} sessões · {total.toFixed(0)} m².</p>
        <table>
          <thead><tr><th>Início</th><th>Duração</th><th>Área</th><th>Bateria</th><th>Resultado</th><th>Origem</th></tr></thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id}>
                <td>{new Date(s.start_ts * 1000).toLocaleString()}</td>
                <td>{s.duration_min ?? "—"} min</td><td>{s.area_m2 ?? "—"} m²</td>
                <td>{s.start_battery ?? "?"}% → {s.end_battery ?? "?"}%</td><td>{s.result ?? "em andamento"}</td>
                <td>{s.simulated ? <span className="badge sim">simulado</span> : "real"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
