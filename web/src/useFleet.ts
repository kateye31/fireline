import { useCallback, useEffect, useRef, useState } from "react";
import { api, Incident, LinkPacket, LiveMessage, Settings, Unit } from "./api";

type Listener = (m: LiveMessage) => void;

/** Loads fleet state over REST, then keeps it current from the /ws stream. */
export function useFleet() {
  const [units, setUnits] = useState<Record<string, Unit>>({});
  const [incidents, setIncidents] = useState<Record<number, Incident>>({});
  const [packets, setPackets] = useState<LinkPacket[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [connected, setConnected] = useState(false);
  const listeners = useRef(new Set<Listener>());

  const subscribe = useCallback((fn: Listener) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  }, []);

  const reload = useCallback(async () => {
    const [u, i, p, s] = await Promise.all([api.units(), api.incidents(), api.packets(), api.settings()]);
    setUnits(Object.fromEntries(u.map((x) => [x.id, x])));
    setIncidents(Object.fromEntries(i.map((x) => [x.id, x])));
    setPackets(p);
    setSettings(s);
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: number | undefined;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => {
        retry = 0;
        setConnected(true);
        reload().catch(console.error); // catch up on anything missed while disconnected
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) timer = window.setTimeout(connect, Math.min(10000, 500 * 2 ** retry++));
      };
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data) as LiveMessage;
        switch (m.type) {
          case "unit":
            setUnits((s) => ({ ...s, [m.data.id]: m.data }));
            break;
          case "unit_removed":
            setUnits((s) => {
              const next = { ...s };
              delete next[m.data.id];
              return next;
            });
            break;
          case "incident":
            setIncidents((s) => ({ ...s, [m.data.id]: { ...s[m.data.id], ...m.data } }));
            break;
          case "packet":
            setPackets((s) => [m.data, ...s.filter((p) => p.id !== m.data.id)].slice(0, 200));
            break;
          case "settings":
            setSettings(m.data);
            break;
          case "reset":
            reload().catch(console.error);
            break;
        }
        listeners.current.forEach((fn) => fn(m));
      };
    };

    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, [reload]);

  return { units, incidents, packets, settings, connected, subscribe, reload };
}

export type Fleet = ReturnType<typeof useFleet>;
