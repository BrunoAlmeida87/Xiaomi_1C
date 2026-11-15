import type { Capabilities, Status } from "../types";
import { useCommand } from "./CommandContext";
import { EvidenceBadge } from "./EvidenceBadge";

const FAN = ["Silencioso", "Padrão", "Médio", "Forte"];
const WATER: Record<number, string> = { 1: "Baixo", 2: "Médio", 3: "Alto" };

function Meter({ label, c }: { label: string; c: { percent: number | null; hours_left: number | null } }) {
  const p = c.percent ?? 0;
  return (
    <div className="meter">
      <div className="row between"><span>{label}</span><span>{c.percent ?? "—"}% · {c.hours_left ?? "—"} h</span></div>
      <div className="bar"><div style={{ width: `${p}%`, background: p < 15 ? "var(--bad)" : "var(--accent)" }} /></div>
    </div>
  );
}

export function Dashboard({ status, caps }: { status: Status | null; caps: Capabilities | null }) {
  const { run } = useCommand();
  const ev = (id: string) => caps?.commands.find((c) => c.id === id)?.evidence;
  const Btn = ({ id, children, cls }: { id: string; children: string; cls?: string }) => (
    <button className={cls} onClick={() => run(id)} title={caps?.commands.find((c) => c.id === id)?.notes}>
      {children} {ev(id) && ev(id) !== "documented_model" && ev(id) !== "verified" && <EvidenceBadge e={ev(id)!} />}
    </button>
  );
  if (!status) return <div className="card">Aguardando dados do robô…</div>;
  return (
    <div className="grid">
      <div className="card">
        <h2>Estado {status.simulated && <span className="badge sim">SIMULADO</span>}</h2>
        <div className="big">{status.status_label ?? "—"}</div>
        <div className="muted">Modo: {status.mode_label ?? "—"} · Carga: {status.charging_label ?? "—"}</div>
        <div className="battery"><div style={{ width: `${status.battery ?? 0}%` }} /><span>{status.battery ?? "—"}%</span></div>
        {status.error ? <div className="error-box">Erro {status.error} ({status.error_name}): {status.error_label}</div> : <div className="muted">Sem erros</div>}
        <div className="row wrap">
          <Btn id="start" cls="primary">Iniciar</Btn>
          <Btn id="pause">Pausar</Btn>
          <Btn id="resume">Continuar</Btn>
          <Btn id="stop">Parar</Btn>
          <Btn id="home">Voltar à base</Btn>
          <Btn id="locate">Localizar</Btn>
        </div>
      </div>
      <div className="card">
        <h2>Configuração de limpeza</h2>
        <label>Potência de sucção</label>
        <div className="row wrap">
          {FAN.map((f, i) => (
            <button key={f} className={status.fan_speed === i ? "selected" : ""} onClick={() => run("set_fan_speed", { value: i })}>{f}</button>
          ))}
        </div>
        <label>Fluxo de água (pano) {ev("set_water_flow") && <EvidenceBadge e={ev("set_water_flow")!} />}</label>
        <div className="row wrap">
          {[1, 2, 3].map((w) => (
            <button key={w} className={status.water_flow === w ? "selected" : ""} onClick={() => run("set_water_flow", { value: w })}>{WATER[w]}</button>
          ))}
        </div>
        <label>Volume: {status.volume ?? "—"}%</label>
        <input type="range" min={0} max={100} defaultValue={status.volume ?? 50}
          onMouseUp={(e) => run("set_volume", { value: Number((e.target as HTMLInputElement).value) })} />
      </div>
      <div className="card">
        <h2>Limpeza atual</h2>
        <div className="stats">
          <div><b>{status.cleaning_area_m2 ?? "—"}</b><span>m² limpos</span></div>
          <div><b>{status.cleaning_time_min ?? "—"}</b><span>minutos</span></div>
        </div>
        <h2>Totais</h2>
        <div className="stats">
          <div><b>{status.total_clean_count ?? "—"}</b><span>limpezas</span></div>
          <div><b>{status.total_clean_area_m2 ?? "—"}</b><span>m² totais</span></div>
          <div><b>{status.total_clean_time_min != null ? Math.round(status.total_clean_time_min / 60) : "—"}</b><span>horas</span></div>
        </div>
      </div>
      <div className="card">
        <h2>Manutenção</h2>
        <Meter label="Escova principal" c={status.consumables.main_brush} />
        <Meter label="Escova lateral" c={status.consumables.side_brush} />
        <Meter label="Filtro" c={status.consumables.filter} />
        <div className="row wrap">
          <button onClick={() => run("reset_main_brush")}>Zerar escova principal</button>
          <button onClick={() => run("reset_side_brush")}>Zerar escova lateral</button>
          <button onClick={() => run("reset_filter")}>Zerar filtro</button>
        </div>
      </div>
      <div className="card span2">
        <h2>Todas as propriedades lidas</h2>
        <table>
          <thead><tr><th>siid.piid</th><th>Propriedade</th><th>Valor</th><th>Evidência</th></tr></thead>
          <tbody>
            {status.properties.map((p) => (
              <tr key={p.key} className={p.code !== 0 ? "dim" : ""}>
                <td>{p.siid}.{p.piid}</td><td>{p.label}</td>
                <td>{p.code === 0 ? `${String(p.display)}${p.unit ? " " + p.unit : ""}` : `sem resposta (code ${p.code})`}</td>
                <td><EvidenceBadge e={p.evidence} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
