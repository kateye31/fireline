import { Unit } from "../api";
import { STATUS_LABEL } from "../format";

const ORDER = ["sleep", "scan", "critical", "alert", "offline"] as const;

/** Marker colour key, bottom-left of the map. */
export function Legend() {
  return (
    <div className="legend glass" aria-label="Map legend">
      {ORDER.map((s) => (
        <div key={s}>
          <span className={`dot dot-${s}`} /> {STATUS_LABEL[s]}
        </div>
      ))}
      <hr />
      <div>
        <span className="real-key" /> Real unit
      </div>
      <div>
        <span className="sim-key" /> Simulated unit
      </div>
    </div>
  );
}

/** At-a-glance fleet numbers, top-left of the map. */
export function FleetStrip({ units, openCount }: { units: Unit[]; openCount: number }) {
  const online = units.filter((u) => u.status !== "offline").length;
  const scanning = units.filter((u) => u.status === "scan" || u.status === "critical").length;
  const driest = units.reduce<number | null>((m, u) => (u.rh !== null && (m === null || u.rh < m) ? u.rh : m), null);

  return (
    <div className="fleet-strip glass">
      <div>
        <small>Online</small>
        <b>
          {online}/{units.length}
        </b>
      </div>
      <div className={scanning ? "warm" : ""}>
        <small>Scanning</small>
        <b>{scanning}</b>
      </div>
      <div className={openCount ? "hot" : ""}>
        <small>Open alerts</small>
        <b>{openCount}</b>
      </div>
      <div className={driest !== null && driest < 30 ? "warm" : ""}>
        <small>Driest</small>
        <b>{driest === null ? "–" : `${driest.toFixed(0)}%`}</b>
      </div>
    </div>
  );
}
