import { Unit } from "../api";
import { ago, byUrgency, num, RISK_LABEL, STATUS_LABEL } from "../format";

export default function UnitList({ units, onSelect }: { units: Unit[]; onSelect: (id: string) => void }) {
  const sorted = [...units].sort(byUrgency);
  const live = units.filter((u) => u.status !== "offline").length;
  const sims = units.filter((u) => u.sim).length;

  return (
    <div className="panel-body">
      <div className="panel-head">
        <h2>Fleet</h2>
        <span className="muted">
          {live}/{units.length} online{sims ? ` · ${sims} simulated` : ""}
        </span>
      </div>
      {sorted.length === 0 && (
        <p className="empty">
          No units yet. Start the simulated fleet with <code>python tools/fake_fleet.py fleet</code> or power on a
          field unit.
        </p>
      )}
      <ul className="unit-list">
        {sorted.map((u) => (
          <li key={u.id}>
            <button className={`unit-row row-${u.status}`} onClick={() => onSelect(u.id)}>
              <span className={`dot dot-${u.status}`} />
              <span className="unit-id">
                {u.id}
                {u.sim ? <span className="tag">SIM</span> : <span className="tag tag-real">REAL</span>}
                <small>{u.loc ?? (u.name !== u.id ? u.name : "")}</small>
              </span>
              <span className="unit-wx">
                {num(u.temp, 1, "°")} · {num(u.rh, 0, "%")}
                <small>
                  {u.risk ? RISK_LABEL[u.risk] : "–"} · {u.status === "offline" ? ago(u.last_seen) : STATUS_LABEL[u.status]}
                </small>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
