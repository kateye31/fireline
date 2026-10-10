import { useState } from "react";
import { api, Incident, Settings, Unit } from "../api";
import { ago, num, RISK_LABEL } from "../format";
import { Pines } from "./Icons";

type Filter = "open" | "all";

export default function AlertFeed({
  incidents,
  units,
  settings,
  onShowUnit,
}: {
  incidents: Incident[];
  units: Record<string, Unit>;
  settings: Settings | null;
  onShowUnit: (id: string) => void;
}) {
  const [filter, setFilter] = useState<Filter>("open");
  const list = incidents
    .filter((i) => filter === "all" || i.status !== "resolved")
    .sort((a, b) => b.opened_at - a.opened_at);

  return (
    <div className="feed">
      <div className="feed-head">
        <div>
          <h2>Alerts</h2>
          <p>Confirmed smoke detections, newest first.</p>
        </div>
        <div className="seg">
          <button className={filter === "open" ? "on" : ""} onClick={() => setFilter("open")}>
            Open
          </button>
          <button className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>
            All
          </button>
        </div>
      </div>
      {list.length === 0 && (
        <div className="empty-state">
          <Pines />
          <b>Quiet forest</b>
          No {filter === "open" ? "open " : ""}incidents. Every unit is watching.
        </div>
      )}
      {list.map((i) => (
        <IncidentCard key={i.id} inc={i} unit={units[i.unit_id]} gemma={settings?.gemma_model ?? null} onShowUnit={onShowUnit} />
      ))}
    </div>
  );
}

function IncidentCard({
  inc,
  unit,
  gemma,
  onShowUnit,
}: {
  inc: Incident;
  unit?: Unit;
  gemma: string | null;
  onShowUnit: (id: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const run = (fn: () => Promise<unknown>) => {
    setBusy(true);
    fn()
      .catch((e) => alert(e))
      .finally(() => setBusy(false));
  };

  return (
    <article className={`card card-${inc.status}`}>
      <div className="card-media">
        {inc.snapshot_id ? (
          <img src={api.snapshotUrl(inc.snapshot_id)} alt={`Smoke crop from ${inc.unit_id}`} />
        ) : (
          <div className="no-snap">no snapshot</div>
        )}
      </div>
      <div className="card-body">
        <header>
          <b>#{inc.id} · {inc.unit_id}</b>
          {unit?.sim ? <span className="tag">SIM</span> : null}
          <span className={`tag tag-${inc.status}`}>{inc.status}</span>
          <span className="muted right">{ago(inc.opened_at)}</span>
        </header>
        <div className="metrics">
          <div>
            <small>Interest</small>
            <b>{num(inc.peak_interest, 2)}</b>
            <div className="meter">
              <i style={{ width: `${Math.min(100, (inc.peak_interest ?? 0) * 100)}%` }} />
            </div>
          </div>
          <div>
            <small>Frames</small>
            <b>{inc.fr ?? "–"}/6</b>
          </div>
          <div>
            <small>Confidence</small>
            <b>{num(inc.conf, 2)}</b>
          </div>
          <div>
            <small>{inc.risk ? `${RISK_LABEL[inc.risk]} risk` : "Weather"}</small>
            <b>
              {num(inc.temp, 0, "°")} · {num(inc.rh, 0, "%")}
            </b>
          </div>
        </div>
        {inc.ai_summary ? (
          <p className="summary ai">
            <span className="tag tag-ai" title={inc.ai_model ?? ""}>
              Gemma
            </span>
            {inc.ai_summary}
          </p>
        ) : (
          <p className="summary">{inc.summary}</p>
        )}
        {inc.ai_summary && <p className="summary-template muted">{inc.summary}</p>}
        <footer>
          <button onClick={() => onShowUnit(inc.unit_id)}>Show on map</button>
          {inc.status === "new" && (
            <button className="primary" disabled={busy} onClick={() => run(() => api.ack(inc.id))}>
              Acknowledge
            </button>
          )}
          {inc.status !== "resolved" && (
            <button disabled={busy} onClick={() => run(() => api.resolve(inc.id))}>
              Resolve
            </button>
          )}
          {gemma && (
            <button className="link" disabled={busy} onClick={() => run(() => api.summarize(inc.id))}>
              {inc.ai_summary ? "Re-ask Gemma" : "Ask Gemma"}
            </button>
          )}
        </footer>
      </div>
    </article>
  );
}
