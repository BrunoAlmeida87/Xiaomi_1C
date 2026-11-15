import { useEffect, useState } from "react";
import { api } from "../api";

interface Probe { timestamp: number; simulated: boolean; info: Record<string, unknown>; model_confirmed: boolean; readable: { siid: number; piid: number; value: unknown; known_as: string | null }[]; unknown_readable: unknown[]; error_codes: Record<string, number> }
interface Audit { id: number; ts: number; command: string; ok: boolean; simulated: boolean; data: { sent: unknown; response: unknown } }

export function DiagnosticsView() {
  const [probe, setProbe] = useState<Probe | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.get<Probe | null>("/api/probe/latest").then(setProbe); api.get<Audit[]>("/api/audit").then(setAudit); }, []);
  const runProbe = async () => {
    setBusy(true); setErr(null);
    try { setProbe(await api.post<Probe>("/api/probe")); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <div className="card">
        <h2>Diagnóstico somente-leitura</h2>
        <p className="small">Lê <code>miIO.info</code> e varre siid 1–30 × piid 1–25 com <code>get_properties</code>. Não envia ações nem escritas. Leva ~1 min no robô real.</p>
        <button className="primary" disabled={busy} onClick={runProbe}>{busy ? "Executando…" : "Executar diagnóstico"}</button>
        {err && <div className="error-box">{err}</div>}
        {probe && (
          <>
            <p>Modelo: <b className="mono">{String(probe.info.model ?? "?")}</b> — {probe.model_confirmed ? <span className="ok">confirmado mc1808</span> : <span className="bad">não confirmado</span>} · Firmware <b>{String(probe.info.fw_ver ?? "?")}</b> {probe.simulated && <span className="badge sim">SIMULADO</span>}</p>
            <p className="small">{probe.readable.length} propriedades legíveis; {probe.unknown_readable.length} fora da base de conhecimento. Códigos de erro: {JSON.stringify(probe.error_codes)}</p>
            <table>
              <thead><tr><th>siid.piid</th><th>Conhecida como</th><th>Valor bruto</th></tr></thead>
              <tbody>{probe.readable.map((r) => (
                <tr key={`${r.siid}.${r.piid}`} className={r.known_as ? "" : "highlight"}>
                  <td className="mono">{r.siid}.{r.piid}</td><td>{r.known_as ?? "desconhecida"}</td><td className="mono small">{JSON.stringify(r.value)}</td>
                </tr>))}
              </tbody>
            </table>
          </>
        )}
      </div>
      <div className="card">
        <h2>Auditoria de comandos</h2>
        <table>
          <thead><tr><th>Quando</th><th>Comando</th><th>Aceito</th><th>Origem</th><th>Enviado</th></tr></thead>
          <tbody>{audit.map((a) => (
            <tr key={a.id}><td>{new Date(a.ts * 1000).toLocaleString()}</td><td>{a.command}</td><td>{a.ok ? "sim" : "não"}</td>
              <td>{a.simulated ? "simulado" : "real"}</td><td className="mono small">{JSON.stringify(a.data.sent)}</td></tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
