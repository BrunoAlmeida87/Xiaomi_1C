import { createContext, useContext, useState, type ReactNode } from "react";
import { api, ApiError } from "../api";
import type { Capabilities, CommandInfo } from "../types";
import { EvidenceBadge } from "./EvidenceBadge";

interface Pending { cmd: CommandInfo; params: Record<string, unknown>; summary?: string; resolve: (ok: boolean) => void }
interface Feedback { cmd: CommandInfo; ok: boolean; message: string; askVerify: boolean }

const Ctx = createContext<{ run: (id: string, params?: Record<string, unknown>, summary?: string) => Promise<boolean> }>({
  run: async () => false,
});
export const useCommand = () => useContext(Ctx);

export function CommandProvider({ caps, simulated, children, onDone }: {
  caps: Capabilities | null; simulated: boolean; children: ReactNode; onDone: () => void;
}) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [busy, setBusy] = useState(false);

  const send = async (cmd: CommandInfo, params: Record<string, unknown>, confirm: boolean) => {
    setBusy(true);
    try {
      const r = await api.command(cmd.id, params, confirm);
      setFeedback({
        cmd, ok: r.ok,
        message: r.ok ? `Aceito pelo ${r.simulated ? "SIMULADOR" : "robô"}. ${r.note}` : `Resposta não-OK: ${JSON.stringify(r.response)}`,
        askVerify: r.ok && !r.simulated && cmd.evidence !== "verified",
      });
      onDone();
      return r.ok;
    } catch (e) {
      const err = e as ApiError;
      setFeedback({ cmd, ok: false, message: err.message, askVerify: false });
      return false;
    } finally { setBusy(false); }
  };

  const run = (id: string, params: Record<string, unknown> = {}, summary?: string) => {
    const cmd = caps?.commands.find((c) => c.id === id);
    if (!cmd) { setFeedback({ cmd: { id, label: id } as CommandInfo, ok: false, message: "Capacidades ainda não carregadas", askVerify: false }); return Promise.resolve(false); }
    if (cmd.evidence === "not_implemented") {
      setFeedback({ cmd, ok: false, message: `Não suportado pelo firmware original: ${cmd.notes}`, askVerify: false });
      return Promise.resolve(false);
    }
    if (!cmd.requires_confirmation) return send(cmd, params, false);
    return new Promise<boolean>((resolve) => setPending({ cmd, params, summary, resolve }));
  };

  const verify = async (worked: boolean) => {
    if (!feedback) return;
    await api.post(`/api/commands/${feedback.cmd.id}/verify`, { worked, notes: "" });
    setFeedback(null);
    onDone();
  };

  return (
    <Ctx.Provider value={{ run }}>
      {children}
      {pending && (
        <div className="modal-bg">
          <div className="modal">
            <h3>Confirmar: {pending.cmd.label}</h3>
            <p className={simulated ? "banner sim" : "banner real"}>
              {simulated ? "Modo SIMULADOR — nenhum comando vai ao robô." : "ROBÔ REAL — este comando será enviado ao equipamento."}
            </p>
            <p><EvidenceBadge e={pending.cmd.evidence} /> {pending.cmd.evidence_label}</p>
            {pending.cmd.moves_robot && <p className="warn">⚠ O robô vai se mover. Verifique se o caminho está livre.</p>}
            {pending.summary && <p>{pending.summary}</p>}
            {pending.cmd.notes && <p className="muted small">{pending.cmd.notes}</p>}
            <details><summary>Parâmetros</summary><pre>{JSON.stringify(pending.params, null, 2)}</pre></details>
            <div className="row end">
              <button onClick={() => { pending.resolve(false); setPending(null); }}>Cancelar</button>
              <button className="primary" disabled={busy} onClick={async () => {
                const p = pending; setPending(null); p.resolve(await send(p.cmd, p.params, true));
              }}>Confirmar e enviar</button>
            </div>
          </div>
        </div>
      )}
      {feedback && (
        <div className={`toast ${feedback.ok ? "ok" : "err"}`}>
          <b>{feedback.cmd.label}:</b> {feedback.message}
          {feedback.askVerify && (
            <div className="row">
              <span>O robô executou fisicamente?</span>
              <button onClick={() => verify(true)}>Sim, funcionou</button>
              <button onClick={() => verify(false)}>Não</button>
            </div>
          )}
          <button className="link" onClick={() => setFeedback(null)}>fechar</button>
        </div>
      )}
    </Ctx.Provider>
  );
}
