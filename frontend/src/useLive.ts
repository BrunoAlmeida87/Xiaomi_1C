import { useEffect, useRef, useState } from "react";
import type { Status } from "./types";

// WebSocket com reconexão automática (backoff exponencial até 30 s).
export function useLive(onMap: () => void) {
  const [status, setStatus] = useState<Status | null>(null);
  const [connection, setConnection] = useState<{ state: string; error: string | null } | null>(null);
  const [wsUp, setWsUp] = useState(false);
  const onMapRef = useRef(onMap);
  onMapRef.current = onMap;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 1000;
    let timer: number | undefined;
    let closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => { setWsUp(true); retry = 1000; };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "status") setStatus(msg.data);
        else if (msg.type === "connection") setConnection(msg.data);
        else if (msg.type === "map") onMapRef.current();
      };
      ws.onclose = () => {
        setWsUp(false);
        if (!closed) { timer = window.setTimeout(connect, retry); retry = Math.min(retry * 2, 30000); }
      };
    };
    connect();
    return () => { closed = true; window.clearTimeout(timer); ws?.close(); };
  }, []);

  return { status, setStatus, connection, wsUp };
}
