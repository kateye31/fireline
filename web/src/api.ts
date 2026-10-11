// Shapes returned by the FastAPI server (server/app/main.py).

export type UnitStatus = "sleep" | "scan" | "critical" | "alert" | "offline";
export type Risk = "low" | "elev" | "crit";

export interface Unit {
  id: string;
  name: string | null;
  lat: number | null;
  lon: number | null;
  loc: string | null;
  sim: number;
  online: number;
  last_seen: number | null;
  last_t: number | null;
  st: "sleep" | "scan" | "alert" | null;
  risk: Risk | null;
  temp: number | null;
  rh: number | null;
  bat: number | null;
  up: number | null;
  open_incidents: number;
  status: UnitStatus;
}

export interface Heartbeat {
  t: number;
  received_at: number;
  st: string | null;
  risk: Risk | null;
  temp: number | null;
  rh: number | null;
  bat: number | null;
}

export interface FireEvent {
  id: number;
  unit_id: string;
  seq: number;
  t: number;
  received_at: number;
  typ: "evt" | "tmp";
  cls: string | null;
  conf: number | null;
  interest: number | null;
  fr: number | null;
  risk: Risk | null;
  temp: number | null;
  rh: number | null;
  box: number[] | null;
  bytes: number;
  delay: number;
  incident_id: number | null;
}

export interface Incident {
  id: number;
  unit_id: string;
  status: "new" | "acknowledged" | "resolved";
  opened_at: number;
  updated_at: number;
  last_event_at: number;
  event_count: number;
  peak_interest: number | null;
  conf: number | null;
  fr: number | null;
  risk: Risk | null;
  temp: number | null;
  rh: number | null;
  lat: number | null;
  lon: number | null;
  snapshot_id: number | null;
  summary: string | null;
  ai_summary: string | null;
  ai_model: string | null;
  is_new?: boolean;
}

export interface LinkPacket {
  id: number;
  unit_id: string | null;
  seq: number | null;
  typ: string | null;
  bytes: number;
  accepted_at: number;
  delivered_at: number | null;
  delay: number | null;
  status: "in_flight" | "delivered" | "duplicate" | "rejected" | "invalid" | "dropped";
  error: string | null;
}

export interface Settings {
  max_bytes: number;
  delay_min: number;
  delay_max: number;
  drop_rate: number;
  demo_mode: boolean;
  offline_after_s: number;
  incident_threshold: number;
  gemma_model: string | null;
}

export interface UnitDetail {
  unit: Unit;
  heartbeats: Heartbeat[];
  events: FireEvent[];
  packets: LinkPacket[];
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? body.error ?? `${r.status} ${r.statusText}`);
  }
  return r.json();
}

export const api = {
  units: () => req<Unit[]>("/api/units"),
  unit: (id: string) => req<UnitDetail>(`/api/units/${encodeURIComponent(id)}`),
  incidents: () => req<Incident[]>("/api/incidents"),
  packets: () => req<LinkPacket[]>("/api/packets"),
  settings: () => req<Settings>("/api/settings"),
  saveSettings: (s: Partial<Settings>) => req<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(s) }),
  ack: (id: number) => req<Incident>(`/api/incidents/${id}/ack`, { method: "POST" }),
  resolve: (id: number) => req<Incident>(`/api/incidents/${id}/resolve`, { method: "POST" }),
  summarize: (id: number) => req<Incident>(`/api/incidents/${id}/summarize`, { method: "POST" }),
  addUnit: (u: { id: string; name?: string; lat: number; lon: number }) =>
    req<Unit>("/api/units", { method: "POST", body: JSON.stringify(u) }),
  deleteUnit: (id: string) => req<{ ok: boolean }>(`/api/units/${encodeURIComponent(id)}`, { method: "DELETE" }),
  resetDemo: () => req<{ ok: boolean }>("/api/demo/reset", { method: "POST" }),
  snapshotUrl: (id: number) => `/api/snapshots/${id}`,
};

export type LiveMessage =
  | { type: "unit"; data: Unit }
  | { type: "unit_removed"; data: { id: string } }
  | { type: "incident"; data: Incident }
  | { type: "event"; data: FireEvent }
  | { type: "packet"; data: LinkPacket }
  | { type: "heartbeat"; data: Heartbeat & { unit_id: string } }
  | { type: "settings"; data: Settings }
  | { type: "reset"; data: Record<string, never> };
