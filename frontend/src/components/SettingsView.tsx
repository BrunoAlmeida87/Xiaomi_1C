import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppState } from "../types";

interface CloudDevice { did: string; name: string; model: string; localip: string; server: string; has_token: boolean; is_1c: boolean; isOnline: boolean }

export function SettingsView({ state, reload }: { state: AppState | null; reload: () => void }) {
  const [ip, setIp] = useState("");
  const [token, setToken] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [qr, setQr] = useState<{ qr_png: string; login_url: string } | null>(null);
  const [qrState, setQrState] = useState<string>("idle");
  const [server, setServer] = useState("");
  const [devices, setDevices] = useState<CloudDevice[] | null>(null);
  const [found, setFound] = useState<{ ip: string; device_id: number }[] | null>(null);

  useEffect(() => { if (state) setIp(state.settings.robot_ip); }, [state]);
  useEffect(() => {
    if (!qr || qrState === "done") return;
    const t = window.setInterval(async () => {
      const s = await api.get<{ state: string; has_cloud_session: boolean }>("/api/cloud/qr/status");
      setQrState(s.state);
      if (s.has_cloud_session && s.state === "done") { setQr(null); reload(); }
    }, 2000);
    return () => window.clearInterval(t);
  }, [qr, qrState, reload]);

  if (!state) return null;
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { setMsg(null); await fn(); setMsg(ok); reload(); } catch (e) { setMsg((e as Error).message); }
  };

  return (
    <div className="stack">
      {msg && <div className="card notice">{msg}</div>}
      <div className="card">
        <h2>Modo de operação</h2>
        <div className="row">
          <button className={state.settings.mode === "simulator" ? "selected" : ""} onClick={() => act(() => api.put("/api/settings", { mode: "simulator" }), "Modo simulador ativo")}>Simulador</button>
          <button className={state.settings.mode === "real" ? "selected" : ""} onClick={() => act(() => api.put("/api/settings", { mode: "real" }), "Modo robô real ativo")}>Robô real</button>
        </div>
        <p className="small">Conexão: <b>{state.connection.state}</b> {state.connection.error && `— ${state.connection.error}`}</p>
        {!state.secrets_persistent && <p className="warn small">Cofre do sistema indisponível: segredos ficam só em memória até fechar o app.</p>}
      </div>

      <div className="card">
        <h2>1. Login na Xiaomi Cloud (QR code)</h2>
        <p className="small">Usado para obter o token local e o mapa. Sua senha nunca passa por este app: escaneie o QR com o app <b>Xiaomi Home</b> (Perfil → ícone de leitura).</p>
        {state.has_cloud_session ? (
          <div className="row"><span className="ok">Sessão ativa (guardada no cofre do Windows).</span>
            <button onClick={() => act(() => api.del("/api/cloud/session"), "Sessão removida")}>Sair</button></div>
        ) : (
          <button className="primary" onClick={() => act(async () => { const r = await api.post<{ qr_png: string; login_url: string }>("/api/cloud/qr/start"); setQr(r); setQrState("waiting"); }, "Escaneie o QR code")}>Gerar QR code</button>
        )}
        {qr && <div className="qr"><img src={qr.qr_png} alt="QR code de login Xiaomi" /><p className="small">Estado: {qrState}. Ou abra: <a href={qr.login_url} target="_blank" rel="noreferrer">link de login</a></p></div>}
      </div>

      <div className="card">
        <h2>2. Importar o robô da conta</h2>
        <div className="row">
          <select value={server} onChange={(e) => setServer(e.target.value)}>
            <option value="">Todos os servidores</option>
            {state.cloud_servers.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button disabled={!state.has_cloud_session} onClick={() => act(async () => setDevices(await api.get(`/api/cloud/devices${server ? `?server=${server}` : ""}`)), "Dispositivos listados")}>Listar dispositivos</button>
        </div>
        {devices && (
          <table>
            <thead><tr><th>Nome</th><th>Modelo</th><th>IP</th><th>Servidor</th><th></th></tr></thead>
            <tbody>{devices.map((d) => (
              <tr key={d.did} className={d.is_1c ? "" : "dim"}>
                <td>{d.name}</td><td className="mono">{d.model}</td><td>{d.localip}</td><td>{d.server}</td>
                <td>{d.is_1c && d.has_token && <button className="primary" onClick={() => act(() => api.post("/api/cloud/devices/import", { did: d.did, server: d.server }), "Robô importado: token guardado no cofre. Selecione 'Robô real'.")}>Importar</button>}</td>
              </tr>))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Configuração manual (alternativa)</h2>
        <div className="row wrap">
          <input placeholder="IP do robô (ex.: 192.168.1.50)" value={ip} onChange={(e) => setIp(e.target.value)} />
          <button onClick={() => act(() => api.put("/api/settings", { robot_ip: ip }), "IP salvo")}>Salvar IP</button>
          <button onClick={() => act(async () => setFound(await api.post("/api/discover")), "Busca concluída")}>Procurar na rede</button>
        </div>
        {found && <p className="small">{found.length ? found.map((f) => `${f.ip} (id ${f.device_id})`).join(", ") : "Nada encontrado (o PC precisa estar na mesma rede)."}</p>}
        <div className="row wrap">
          <input type="password" autoComplete="off" placeholder="Token (32 hex) — nunca exibido" value={token} onChange={(e) => setToken(e.target.value)} />
          <button onClick={() => act(async () => { await api.put("/api/secrets/token", { token }); setToken(""); }, "Token guardado no cofre")}>Salvar token</button>
          {state.has_token && <button onClick={() => act(() => api.del("/api/secrets/token"), "Token removido")}>Remover token</button>}
        </div>
        <p className="small">Token configurado: {state.has_token ? "sim" : "não"}.</p>
      </div>

      <div className="card">
        <h2>Segurança e mapa</h2>
        <label><input type="checkbox" checked={state.settings.allow_experimental}
          onChange={(e) => act(() => api.put("/api/settings", { allow_experimental: e.target.checked }), "Preferência salva")} />{" "}
          Permitir comandos experimentais (zona, cômodo, ponto, pausa, controle manual)</label>
        <label><input type="checkbox" checked={state.settings.auto_map_refresh}
          onChange={(e) => act(() => api.put("/api/settings", { auto_map_refresh: e.target.checked }), "Preferência salva")} />{" "}
          Atualizar o mapa automaticamente pela Cloud durante a limpeza (a cada {state.settings.map_refresh_interval_s}s)</label>
      </div>
    </div>
  );
}
