import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { Capabilities, Draft, MapData, Region } from "../types";
import { useCommand } from "./CommandContext";
import { EvidenceBadge } from "./EvidenceBadge";

type Tool = "pan" | "point" | "zone" | "wall" | "nogo";
type Pt = { x: number; y: number };

const ROOM_COLORS = ["#8ecae6", "#ffb703", "#90be6d", "#f4a261", "#cdb4db", "#a8dadc", "#e9c46a", "#b5e48c"];

function decode(b64: string): Uint8Array {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

function hexToRgb(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Renderiza a grade do mapa (1 pixel por célula), invertendo Y (Y do robô cresce para cima). */
function buildBase(map: MapData): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = map.width;
  c.height = map.height;
  const ctx = c.getContext("2d")!;
  const img = ctx.createImageData(map.width, map.height);
  const cls = decode(map.classes_b64);
  const seg = decode(map.segments_b64);
  for (let row = 0; row < map.height; row++) {
    for (let col = 0; col < map.width; col++) {
      const i = row * map.width + col;
      const o = ((map.height - 1 - row) * map.width + col) * 4;
      let rgb: [number, number, number] | null = null;
      if (seg[i]) rgb = hexToRgb(ROOM_COLORS[seg[i] % ROOM_COLORS.length]);
      else if (cls[i] === 1) rgb = [200, 214, 229];
      else if (cls[i] === 2) rgb = [52, 58, 64];
      if (rgb) { img.data[o] = rgb[0]; img.data[o + 1] = rgb[1]; img.data[o + 2] = rgb[2]; img.data[o + 3] = 255; }
    }
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

export function MapView({ caps, mapVersion }: { caps: Capabilities | null; mapVersion: number }) {
  const { run } = useCommand();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("pan");
  const [view, setView] = useState({ scale: 4, panX: 20, panY: 20 });
  const [drag, setDrag] = useState<{ start: Pt; cur: Pt; sx: number; sy: number; pan0?: { x: number; y: number } } | null>(null);
  const [zones, setZones] = useState<number[][]>([]);
  const [repeats, setRepeats] = useState(1);
  const [point, setPoint] = useState<Pt | null>(null);
  const [selectedRooms, setSelectedRooms] = useState<number[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [history, setHistory] = useState<{ id: number; ts: number; source: string; simulated: boolean }[]>([]);
  const [cursor, setCursor] = useState<Pt | null>(null);
  const [layers, setLayers] = useState({ path: true, restrictions: true, drafts: true, rooms: true });

  const base = useMemo(() => (map ? buildBase(map) : null), [map]);

  const loadAux = useCallback(async () => {
    setRegions(await api.get<Region[]>("/api/regions"));
    setDrafts(await api.get<Draft[]>("/api/drafts"));
    setHistory(await api.get("/api/maps"));
  }, []);

  const load = useCallback(async (refresh = false) => {
    try {
      setError(null);
      const m = await (refresh ? api.post<MapData>("/api/map/refresh") : api.get<MapData>("/api/map"));
      setMap(m);
      loadAux();
    } catch (e) { setError((e as Error).message); }
  }, [loadAux]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (mapVersion) load(); }, [mapVersion, load]);

  // Ajusta o zoom para caber o mapa ao carregar um mapa de outro tamanho.
  const fitted = useRef<string>("");
  useEffect(() => {
    if (!map || !wrapRef.current) return;
    const key = `${map.width}x${map.height}`;
    if (fitted.current === key) return;
    fitted.current = key;
    const w = wrapRef.current.clientWidth, h = wrapRef.current.clientHeight;
    const scale = Math.max(1, Math.min(w / map.width, h / map.height) * 0.95);
    setView({ scale, panX: (w - map.width * scale) / 2, panY: (h - map.height * scale) / 2 });
  }, [map]);

  // --- conversões de coordenadas (mm do robô <-> tela) ---------------------
  const toScreen = useCallback((x: number, y: number): [number, number] => {
    if (!map) return [0, 0];
    const c = (x - map.left) / map.pixel_size;
    const r = map.height - (y - map.top) / map.pixel_size;
    return [c * view.scale + view.panX, r * view.scale + view.panY];
  }, [map, view]);

  const toMm = useCallback((sx: number, sy: number): Pt => {
    if (!map) return { x: 0, y: 0 };
    const c = (sx - view.panX) / view.scale;
    const r = map.height - (sy - view.panY) / view.scale;
    return { x: Math.round(map.left + c * map.pixel_size), y: Math.round(map.top + r * map.pixel_size) };
  }, [map, view]);

  // --- desenho ----------------------------------------------------------------
  useEffect(() => {
    const cv = canvasRef.current, wrap = wrapRef.current;
    if (!cv || !wrap) return;
    cv.width = wrap.clientWidth;
    cv.height = wrap.clientHeight;
    const ctx = cv.getContext("2d")!;
    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--map-bg") || "#f1f3f5";
    ctx.fillRect(0, 0, cv.width, cv.height);
    if (!map || !base) return;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(base, view.panX, view.panY, map.width * view.scale, map.height * view.scale);

    const rect = (r: number[], stroke: string, fill: string, dash: number[] = []) => {
      const [x0, y0] = toScreen(r[0], r[1]);
      const [x1, y1] = toScreen(r[2], r[3]);
      ctx.setLineDash(dash);
      ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 2;
      ctx.fillRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
      ctx.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
      ctx.setLineDash([]);
    };
    const line = (l: number[], stroke: string, width = 3, dash: number[] = []) => {
      const [x0, y0] = toScreen(l[0], l[1]);
      const [x1, y1] = toScreen(l[2], l[3]);
      ctx.setLineDash(dash); ctx.strokeStyle = stroke; ctx.lineWidth = width;
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.setLineDash([]);
    };

    if (layers.rooms) {
      ctx.font = "12px system-ui"; ctx.textAlign = "center";
      for (const r of map.rooms) {
        const [cx, cy] = toScreen((r.bbox[0] + r.bbox[2]) / 2, (r.bbox[1] + r.bbox[3]) / 2);
        if (selectedRooms.includes(r.id)) rect(r.bbox, "#0b7285", "rgba(11,114,133,0.15)");
        ctx.fillStyle = "#212529"; ctx.fillText(`${r.name} (#${r.id})`, cx, cy);
      }
    }
    if (layers.path) {
      ctx.strokeStyle = "rgba(255,255,255,0.9)"; ctx.lineWidth = 1.2;
      for (const seg of map.path) {
        ctx.beginPath();
        seg.forEach(([x, y], i) => { const [sx, sy] = toScreen(x, y); if (i) ctx.lineTo(sx, sy); else ctx.moveTo(sx, sy); });
        ctx.stroke();
      }
    }
    if (layers.restrictions) {
      // Restrições LIDAS do mapa do robô (campo "vw")
      map.no_go_areas.forEach((a) => rect(a, "#c92a2a", "rgba(201,42,42,0.25)"));
      map.no_mop_areas.forEach((a) => rect(a, "#5f3dc4", "rgba(95,61,196,0.2)"));
      map.virtual_walls.forEach((w) => line(w, "#c92a2a", 4));
    }
    if (layers.drafts) {
      // Rascunhos: SÓ na interface, tracejados
      for (const d of drafts) {
        if (d.kind === "virtual_wall") line(d.data.line, "#e8590c", 3, [6, 4]);
        else rect(d.data.rect, "#e8590c", "rgba(232,89,12,0.12)", [6, 4]);
      }
    }
    zones.forEach((z) => rect(z, "#1971c2", "rgba(25,113,194,0.2)"));
    if (point) {
      const [px, py] = toScreen(point.x, point.y);
      ctx.fillStyle = "#1971c2"; ctx.beginPath(); ctx.arc(px, py, 6, 0, Math.PI * 2); ctx.fill();
    }
    if (drag && tool !== "pan") {
      const r = [drag.start.x, drag.start.y, drag.cur.x, drag.cur.y];
      if (tool === "wall") line(r, "#e8590c", 3, [6, 4]);
      else if (tool === "zone") rect(r, "#1971c2", "rgba(25,113,194,0.2)");
      else if (tool === "nogo") rect(r, "#e8590c", "rgba(232,89,12,0.12)", [6, 4]);
    }
    if (map.charger) {
      const [cx, cy] = toScreen(map.charger.x, map.charger.y);
      ctx.fillStyle = "#2b8a3e"; ctx.fillRect(cx - 6, cy - 6, 12, 12);
    }
    if (map.robot) {
      const [rx, ry] = toScreen(map.robot.x, map.robot.y);
      const rad = Math.max(6, (175 / map.pixel_size) * view.scale);
      ctx.fillStyle = "#f8f9fa"; ctx.strokeStyle = "#343a40"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(rx, ry, rad, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      const a = (map.robot.angle * Math.PI) / 180;
      ctx.beginPath(); ctx.moveTo(rx, ry); ctx.lineTo(rx + Math.cos(a) * rad, ry - Math.sin(a) * rad); ctx.stroke();
    }
  }, [map, base, view, zones, point, drag, tool, drafts, selectedRooms, layers, toScreen]);

  // --- interação ---------------------------------------------------------------
  const local = (e: React.MouseEvent) => {
    const b = canvasRef.current!.getBoundingClientRect();
    return { sx: e.clientX - b.left, sy: e.clientY - b.top };
  };
  const onDown = (e: React.MouseEvent) => {
    const { sx, sy } = local(e);
    const p = toMm(sx, sy);
    if (tool === "point") { setPoint(p); return; }
    setDrag({ start: p, cur: p, sx, sy, pan0: { x: view.panX, y: view.panY } });
  };
  const onMove = (e: React.MouseEvent) => {
    const { sx, sy } = local(e);
    setCursor(toMm(sx, sy));
    if (!drag) return;
    if (tool === "pan" && drag.pan0) setView((v) => ({ ...v, panX: drag.pan0!.x + sx - drag.sx, panY: drag.pan0!.y + sy - drag.sy }));
    else setDrag({ ...drag, cur: toMm(sx, sy) });
  };
  const onUp = async () => {
    if (!drag) return;
    const r = [drag.start.x, drag.start.y, drag.cur.x, drag.cur.y];
    const norm = [Math.min(r[0], r[2]), Math.min(r[1], r[3]), Math.max(r[0], r[2]), Math.max(r[1], r[3])];
    setDrag(null);
    if (tool === "zone" && norm[2] - norm[0] >= 300 && norm[3] - norm[1] >= 300) setZones((z) => [...z, norm]);
    if (tool === "wall" && Math.hypot(r[2] - r[0], r[3] - r[1]) > 200) {
      await api.post("/api/drafts", { name: `Parede ${drafts.length + 1}`, kind: "virtual_wall", data: { line: r } });
      loadAux();
    }
    if (tool === "nogo" && norm[2] - norm[0] >= 200) {
      await api.post("/api/drafts", { name: `Zona proibida ${drafts.length + 1}`, kind: "no_go", data: { rect: norm } });
      loadAux();
    }
  };
  const onWheel = (e: React.WheelEvent) => {
    const { sx, sy } = local(e);
    const f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    setView((v) => {
      const scale = Math.min(40, Math.max(0.5, v.scale * f));
      const k = scale / v.scale;
      return { scale, panX: sx - (sx - v.panX) * k, panY: sy - (sy - v.panY) * k };
    });
  };

  const ev = (id: string) => caps?.commands.find((c) => c.id === id)?.evidence;
  const toggleRoom = (id: number) => setSelectedRooms((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const saveZones = async () => {
    const name = prompt("Nome da região:", "Perto da mesa");
    if (!name) return;
    await api.post("/api/regions", { name, kind: "zone", data: { zones, repeats } });
    loadAux();
  };
  const saveRoomSeq = async () => {
    const name = prompt("Nome da sequência de cômodos:", "Sala + cozinha");
    if (!name) return;
    await api.post("/api/regions", { name, kind: "room_sequence", data: { rooms: selectedRooms, repeats } });
    loadAux();
  };
  const runRegion = (r: Region) => {
    if (r.kind === "zone") run("clean_zone", { zones: r.data.zones, repeats: r.data.repeats ?? 1 }, `Região salva "${r.name}"`);
    else if (r.kind === "room_sequence") run("clean_rooms", { rooms: r.data.rooms, repeats: r.data.repeats ?? 1 }, `Sequência "${r.name}"`);
    else if (r.kind === "point") run("clean_point", r.data, `Ponto "${r.name}"`);
  };
  const renameRoom = async (id: number, current: string) => {
    const name = prompt("Novo nome (salvo só neste aplicativo):", current);
    if (!name) return;
    await api.put(`/api/rooms/${id}/name`, { name });
    load();
  };

  return (
    <div className="mapview">
      <div className="map-canvas" ref={wrapRef}>
        <canvas ref={canvasRef} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={() => { setDrag(null); setCursor(null); }}
          onWheel={onWheel} style={{ cursor: tool === "pan" ? "grab" : "crosshair" }} />
        <div className="map-overlay">
          {map && <span className={`badge ${map.simulated ? "sim" : "real"}`}>{map.simulated ? "MAPA SIMULADO" : `Mapa: ${map.source}`}</span>}
          {map && <span className="muted small"> {new Date(map.timestamp * 1000).toLocaleString()} · {map.pixel_size} mm/px</span>}
          {cursor && <span className="small"> · x={cursor.x} mm, y={cursor.y} mm</span>}
        </div>
        {error && <div className="error-box overlay-error">{error}</div>}
      </div>
      <aside className="map-side">
        <div className="card">
          <div className="row between"><h3>Ferramentas</h3><button onClick={() => load(true)}>Atualizar mapa</button></div>
          <div className="row wrap">
            {([["pan", "Mover"], ["point", "Ponto"], ["zone", "Zona"], ["wall", "Parede (rascunho)"], ["nogo", "Proibida (rascunho)"]] as [Tool, string][]).map(([t, l]) => (
              <button key={t} className={tool === t ? "selected" : ""} onClick={() => setTool(t)}>{l}</button>
            ))}
          </div>
          <div className="row wrap small">
            {(Object.keys(layers) as (keyof typeof layers)[]).map((k) => (
              <label key={k}><input type="checkbox" checked={layers[k]} onChange={() => setLayers({ ...layers, [k]: !layers[k] })} /> {k}</label>
            ))}
          </div>
          {history.length > 0 && (
            <select onChange={async (e) => { if (e.target.value) setMap(await api.get(`/api/maps/${e.target.value}`)); }} defaultValue="">
              <option value="">Mapas salvos localmente ({history.length})</option>
              {history.map((h) => <option key={h.id} value={h.id}>{new Date(h.ts * 1000).toLocaleString()} · {h.source}</option>)}
            </select>
          )}
        </div>

        {point && (
          <div className="card">
            <h3>Ponto <EvidenceBadge e={ev("clean_point") ?? "experimental"} /></h3>
            <p className="small">x={point.x}, y={point.y} mm. O 1C não tem limpeza por ponto documentada: é enviada uma zona de 1 m × 1 m centrada no ponto.</p>
            <div className="row">
              <button className="primary" onClick={() => run("clean_point", { x: point.x, y: point.y, size: 1000 }, `Ponto (${point.x}, ${point.y})`)}>Limpar aqui</button>
              <button onClick={() => setPoint(null)}>Descartar</button>
            </div>
          </div>
        )}

        <div className="card">
          <h3>Zonas ({zones.length}) <EvidenceBadge e={ev("clean_zone") ?? "experimental"} /></h3>
          {zones.map((z, i) => (
            <div key={i} className="row between small">
              <span>[{z.join(", ")}]</span><button className="link" onClick={() => setZones(zones.filter((_, j) => j !== i))}>remover</button>
            </div>
          ))}
          <label className="small">Repetições <input type="number" min={1} max={3} value={repeats} onChange={(e) => setRepeats(Number(e.target.value))} /></label>
          <div className="row wrap">
            <button className="primary" disabled={!zones.length} onClick={() => run("clean_zone", { zones, repeats }, `${zones.length} zona(s)`)}>Limpar zonas</button>
            <button disabled={!zones.length} onClick={saveZones}>Salvar região</button>
            <button disabled={!zones.length} onClick={() => setZones([])}>Limpar seleção</button>
          </div>
        </div>

        <div className="card">
          <h3>Cômodos <EvidenceBadge e={ev("clean_rooms") ?? "experimental"} /></h3>
          {!map?.rooms.length && <p className="small muted">O mapa não contém cômodos segmentados.</p>}
          {map?.rooms.map((r) => (
            <div key={r.id} className="row between small">
              <label><input type="checkbox" checked={selectedRooms.includes(r.id)} onChange={() => toggleRoom(r.id)} /> {r.name} <span className="muted">#{r.id}</span></label>
              <button className="link" onClick={() => renameRoom(r.id, r.name)}>renomear</button>
            </div>
          ))}
          {selectedRooms.length > 0 && <p className="small">Ordem: {selectedRooms.join(" → ")}</p>}
          <div className="row wrap">
            <button className="primary" disabled={!selectedRooms.length} onClick={() => run("clean_rooms", { rooms: selectedRooms, repeats }, `Cômodos ${selectedRooms.join(", ")}`)}>Limpar cômodos</button>
            <button disabled={!selectedRooms.length} onClick={saveRoomSeq}>Salvar sequência</button>
          </div>
          <p className="small muted">Dividir/unir cômodos: <EvidenceBadge e="not_implemented" /> — nomes ficam só no app.</p>
        </div>

        <div className="card">
          <h3>Regiões salvas</h3>
          {!regions.length && <p className="small muted">Nenhuma.</p>}
          {regions.map((r) => (
            <div key={r.id} className="row between small">
              <span>{r.name} <span className="muted">({r.kind})</span></span>
              <span>
                <button className="link" onClick={() => runRegion(r)}>executar</button>{" "}
                <button className="link" onClick={async () => { await api.del(`/api/regions/${r.id}`); loadAux(); }}>excluir</button>
              </span>
            </div>
          ))}
        </div>

        <div className="card">
          <h3>Restrições</h3>
          <p className="small"><b>No robô (lidas do mapa):</b> {map?.virtual_walls.length ?? 0} parede(s), {map?.no_go_areas.length ?? 0} zona(s) proibida(s), {map?.no_mop_areas.length ?? 0} sem pano — linhas contínuas vermelhas.</p>
          <p className="small"><b>Rascunhos (só nesta interface):</b> tracejados laranja. <EvidenceBadge e="not_implemented" /> Gravar no robô não é suportado — crie-as no Xiaomi Home usando o rascunho como guia.</p>
          {drafts.map((d) => (
            <div key={d.id} className="row between small">
              <span>{d.name} <span className="badge draft">não enviado</span></span>
              <button className="link" onClick={async () => { await api.del(`/api/drafts/${d.id}`); loadAux(); }}>excluir</button>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
