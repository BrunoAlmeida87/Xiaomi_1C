import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { CapabilitiesView } from "./components/CapabilitiesView";
import { CommandProvider } from "./components/CommandContext";
import { Dashboard } from "./components/Dashboard";
import { DiagnosticsView } from "./components/DiagnosticsView";
import { HistoryView } from "./components/HistoryView";
import { MapView } from "./components/MapView";
import { SettingsView } from "./components/SettingsView";
import type { AppState, Capabilities, Status } from "./types";
import { useLive } from "./useLive";

const TABS = [
  ["dashboard", "Painel"], ["map", "Mapa"], ["history", "Histórico"],
  ["caps", "Compatibilidade"], ["diag", "Diagnóstico"], ["settings", "Configurações"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [state, setState] = useState<AppState | null>(null);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [mapVersion, setMapVersion] = useState(0);
  const live = useLive(() => setMapVersion((v) => v + 1));

  const reload = useCallback(async () => {
    setState(await api.get<AppState>("/api/state"));
    setCaps(await api.get<Capabilities>("/api/capabilities"));
    try { live.setStatus(await api.get<Status>("/api/status")); } catch { /* offline: mostrado no cabeçalho */ }
  }, [live.setStatus]);
  useEffect(() => { reload(); }, [reload]);

  const conn = live.connection ?? state?.connection;
  const simulated = state?.simulated ?? true;
  return (
    <CommandProvider caps={caps} simulated={simulated} onDone={reload}>
      <header>
        <h1>Xiaomi 1C Control</h1>
        <nav>{TABS.map(([id, label]) => <button key={id} className={tab === id ? "tab active" : "tab"} onClick={() => setTab(id)}>{label}</button>)}</nav>
        <div className="conn">
          <span className={`badge ${simulated ? "sim" : "real"}`}>{simulated ? "SIMULADOR" : "ROBÔ REAL"}</span>
          <span className={`dot ${conn?.state === "online" ? "on" : "off"}`} /> {conn?.state ?? "…"}
          {!live.wsUp && <span className="small muted"> (reconectando)</span>}
        </div>
      </header>
      {simulated && <div className="banner sim">Modo simulador: todos os dados e o mapa são fictícios. Configure o robô real em Configurações.</div>}
      {!simulated && conn?.state !== "online" && conn?.error && <div className="banner real">{conn.error}</div>}
      <main>
        {tab === "dashboard" && <Dashboard status={live.status} caps={caps} />}
        {tab === "map" && <MapView caps={caps} mapVersion={mapVersion} />}
        {tab === "history" && <HistoryView simulated={simulated} />}
        {tab === "caps" && <CapabilitiesView caps={caps} />}
        {tab === "diag" && <DiagnosticsView />}
        {tab === "settings" && <SettingsView state={state} reload={reload} />}
      </main>
    </CommandProvider>
  );
}
