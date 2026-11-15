import type { Capabilities } from "../types";
import { EvidenceBadge } from "./EvidenceBadge";

export function CapabilitiesView({ caps }: { caps: Capabilities | null }) {
  if (!caps) return <div className="card">Carregando…</div>;
  return (
    <div className="stack">
      <div className="card">
        <h2>Matriz de compatibilidade — {caps.model}</h2>
        <p className="small">
          {caps.probe_available
            ? <>Diagnóstico do robô real executado (firmware {caps.probe_firmware ?? "?"}; modelo {caps.model_confirmed ? "CONFIRMADO" : "NÃO confirmado"}). Propriedades lidas com sucesso aparecem como <EvidenceBadge e="verified" />.</>
            : <>Nenhum diagnóstico do robô real ainda. Nada está marcado como <EvidenceBadge e="verified" /> até você rodar o diagnóstico (aba Diagnóstico) e confirmar fisicamente os comandos.</>}
        </p>
        <p className="small muted">Comandos só viram “Comprovado” quando você confirma que o robô executou fisicamente — “code 0” apenas indica que o firmware aceitou a mensagem.</p>
      </div>
      <div className="card">
        <h3>Comandos</h3>
        <table>
          <thead><tr><th>Função</th><th>Evidência</th><th>MIoT</th><th>Fontes</th><th>Observações</th></tr></thead>
          <tbody>
            {caps.commands.map((c) => (
              <tr key={c.id}>
                <td>{c.label}{c.moves_robot && " 🚶"}</td>
                <td><EvidenceBadge e={c.evidence} />{c.verification && !c.verification.worked && <div className="small bad">Você marcou: não funcionou</div>}</td>
                <td className="mono">{c.siid != null ? `${c.siid}.${c.aiid ?? c.piid ?? ""}` : "—"}</td>
                <td className="small">{c.sources.join(", ")}</td>
                <td className="small">{c.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h3>Propriedades</h3>
        <table>
          <thead><tr><th>siid.piid</th><th>Propriedade</th><th>Acesso</th><th>Evidência</th><th>Observações</th></tr></thead>
          <tbody>
            {caps.properties.map((p) => (
              <tr key={p.key}>
                <td className="mono">{p.siid}.{p.piid}</td><td>{p.label}</td><td className="mono">{p.access}</td>
                <td><EvidenceBadge e={p.evidence} /></td><td className="small">{p.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
