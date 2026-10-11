import { CSSProperties, useEffect, useState } from "react";
import { api, Unit, UnitDetail as Detail } from "../api";
import { Fleet } from "../useFleet";
import { ago, clock, num, RISK_LABEL, STATUS_LABEL } from "../format";
import Chart from "./Chart";

const RISK_TONE: Record<string, string> = {
  low: "var(--c-sleep)",
  elev: "var(--c-scan)",
  crit: "var(--c-critical)",
  none: "var(--c-offline)",
};

export default function UnitDetail({ unit, fleet, onBack }: { unit: Unit; fleet: Fleet; onBack: () => void }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDetail(null);
    api.unit(unit.id).then(setDetail, (e) => setError(String(e)));
  }, [unit.id]);

  // Keep charts, events and the link log live without refetching.
  useEffect(
    () =>
      fleet.subscribe((m) => {
        setDetail((d) => {
          if (!d) return d;
          if (m.type === "heartbeat" && m.data.unit_id === unit.id)
            return { ...d, heartbeats: [...d.heartbeats, { ...m.data, received_at: Date.now() / 1000 }].slice(-500) };
          if (m.type === "event" && m.data.unit_id === unit.id) return { ...d, events: [m.data, ...d.events] };
          if (m.type === "packet" && m.data.unit_id === unit.id)
            return { ...d, packets: [m.data, ...d.packets.filter((p) => p.id !== m.data.id)].slice(0, 100) };
          return d;
        });
      }),
    [fleet, unit.id],
  );

  const hb = detail?.heartbeats ?? [];
  const temp = hb.filter((h) => h.temp !== null).map((h) => ({ t: h.t, v: h.temp! }));
  const rh = hb.filter((h) => h.rh !== null).map((h) => ({ t: h.t, v: h.rh! }));

  return (
    <div className="panel-body">
      <button className="link back" onClick={onBack}>
        ← Fleet
      </button>
      <div className="panel-head">
        <h2>
          <span className={`dot dot-${unit.status}`} /> {unit.id}
          {unit.sim ? <span className="tag">SIM</span> : <span className="tag tag-real">REAL</span>}
        </h2>
        <span className="muted">{unit.loc ?? unit.name}</span>
      </div>

      <div className="stats">
        <div className="stat tone" style={{ "--tone": `var(--c-${unit.status})` } as CSSProperties}>
          <small>State</small>
          <b>{STATUS_LABEL[unit.status]}</b>
        </div>
        <div className="stat tone" style={{ "--tone": RISK_TONE[unit.risk ?? "none"] } as CSSProperties}>
          <small>Fire risk</small>
          <b>{unit.risk ? RISK_LABEL[unit.risk] : "–"}</b>
        </div>
        <div className="stat">
          <small>Battery</small>
          <span className="num">{num(unit.bat, 0, "%")}</span>
        </div>
        <div className="stat">
          <small>Last heard</small>
          {ago(unit.last_seen)}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <Chart points={temp} color="var(--c-temp)" label="Temperature" unit=" °C" guides={[{ v: 30, label: "30 °C" }]} />
      <Chart
        points={rh}
        color="var(--c-rh)"
        label="Humidity"
        unit=" %"
        domain={[0, 100]}
        guides={[
          { v: 50, label: "elevated" },
          { v: 30, label: "critical" },
        ]}
      />

      {hb.length > 0 && (
        <div className="risk-strip" title="Fire-risk tier, oldest to newest">
          {hb.slice(-60).map((h, i) => (
            <span key={i} className={`risk-${h.risk ?? "none"}`} />
          ))}
        </div>
      )}

      <h3>Events</h3>
      {detail && detail.events.length === 0 && <p className="empty">No detections from this unit.</p>}
      <ul className="timeline">
        {detail?.events.slice(0, 20).map((e) => (
          <li key={e.id}>
            <span className="muted">{clock(e.received_at)}</span> <b>{e.cls ?? e.typ}</b>
            {e.interest !== null && ` · interest ${e.interest.toFixed(2)}`}
            {e.fr !== null && ` · ${e.fr}/6 frames`}
            {e.incident_id && <span className="tag tag-alert">incident #{e.incident_id}</span>}
          </li>
        ))}
      </ul>

      <h3>Satellite link log</h3>
      <table className="link-log">
        <thead>
          <tr>
            <th>Seq</th>
            <th>Type</th>
            <th>Size</th>
            <th>Delay</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {detail?.packets.slice(0, 30).map((p) => (
            <tr key={p.id} className={`pkt-${p.status}`} title={p.error ?? ""}>
              <td>{p.seq ?? "–"}</td>
              <td>{p.typ ?? "?"}</td>
              <td>{p.bytes} B</td>
              <td>{p.delay !== null ? `${p.delay.toFixed(1)} s` : "…"}</td>
              <td>{p.status.replace("_", " ")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <button
        className="link danger"
        onClick={() => {
          if (confirm(`Remove ${unit.id} from the map? It reappears on its next heartbeat.`))
            api.deleteUnit(unit.id).then(onBack);
        }}
      >
        Remove unit
      </button>
    </div>
  );
}
