import { Risk, Unit, UnitStatus } from "./api";

export const STATUS_LABEL: Record<UnitStatus, string> = {
  sleep: "Asleep",
  scan: "Scanning",
  critical: "Critical weather",
  alert: "Smoke alert",
  offline: "Offline",
};

export const RISK_LABEL: Record<Risk, string> = { low: "Low", elev: "Elevated", crit: "Critical" };

const STATUS_RANK: Record<UnitStatus, number> = { alert: 0, critical: 1, scan: 2, sleep: 3, offline: 4 };

/** Most urgent first, then driest. */
export function byUrgency(a: Unit, b: Unit) {
  return STATUS_RANK[a.status] - STATUS_RANK[b.status] || (a.rh ?? 100) - (b.rh ?? 100) || a.id.localeCompare(b.id);
}

export function ago(ts: number | null | undefined): string {
  if (!ts) return "never";
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export const num = (v: number | null | undefined, digits = 0, suffix = "") =>
  v === null || v === undefined ? "–" : `${v.toFixed(digits)}${suffix}`;
