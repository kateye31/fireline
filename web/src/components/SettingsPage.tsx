import { FormEvent, useEffect, useState } from "react";
import { api, LinkPacket, Settings } from "../api";
import { clock } from "../format";

export default function SettingsPage({ settings, packets }: { settings: Settings | null; packets: LinkPacket[] }) {
  const [draft, setDraft] = useState<Settings | null>(settings);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => setDraft(settings), [settings]);

  const save = (patch: Partial<Settings>) =>
    api.saveSettings(patch).then(
      () => setMsg("Saved"),
      (e) => setMsg(String(e)),
    );

  const addUnit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const form = e.currentTarget;
    api
      .addUnit({
        id: String(f.get("id")),
        name: String(f.get("name") || "") || undefined,
        lat: Number(f.get("lat")),
        lon: Number(f.get("lon")),
      })
      .then(
        (u) => {
          setMsg(`Added ${u.id}; it shows grey until its first heartbeat.`);
          form.reset();
        },
        (err) => setMsg(String(err)),
      );
  };

  if (!draft) return <div className="settings">Loading…</div>;

  return (
    <div className="settings">
      <section>
        <h2>Demo mode</h2>
        <p className="muted">Shortens the satellite delay to 1–4 s so the whole chain plays out at the judging table.</p>
        <label className="switch">
          <input type="checkbox" checked={draft.demo_mode} onChange={(e) => save({ demo_mode: e.target.checked })} />
          <span>{draft.demo_mode ? "On" : "Off"}</span>
        </label>
      </section>

      <section>
        <h2>Simulated satellite link</h2>
        <div className="grid">
          <label>
            Max packet size (B)
            <input type="number" value={draft.max_bytes} onChange={(e) => setDraft({ ...draft, max_bytes: +e.target.value })} />
          </label>
          <label>
            Delay min (s)
            <input type="number" step="0.5" value={draft.delay_min} onChange={(e) => setDraft({ ...draft, delay_min: +e.target.value })} />
          </label>
          <label>
            Delay max (s)
            <input type="number" step="0.5" value={draft.delay_max} onChange={(e) => setDraft({ ...draft, delay_max: +e.target.value })} />
          </label>
          <label>
            Drop rate (0–1)
            <input type="number" step="0.05" min="0" max="1" value={draft.drop_rate} onChange={(e) => setDraft({ ...draft, drop_rate: +e.target.value })} />
          </label>
        </div>
        <button
          onClick={() =>
            save({ max_bytes: draft.max_bytes, delay_min: draft.delay_min, delay_max: draft.delay_max, drop_rate: draft.drop_rate })
          }
        >
          Save link settings
        </button>
        <p className="muted">
          Incidents open at interest ≥ {draft.incident_threshold}; units go grey after {draft.offline_after_s} s of silence.
          Fire-risk tiers are computed on the ESP32. AI summaries: {draft.gemma_model ?? "off (set GEMMA_BASE_URL)"}.
        </p>
      </section>

      <section>
        <h2>Add a unit</h2>
        <p className="muted">Units also appear on their own with their first heartbeat; use this to pre-place a mounting spot.</p>
        <form className="grid" onSubmit={addUnit}>
          <label>
            ID
            <input name="id" required placeholder="gw-04" />
          </label>
          <label>
            Name
            <input name="name" placeholder="Juniper Prairie" />
          </label>
          <label>
            Latitude
            <input name="lat" type="number" step="any" required placeholder="29.18" />
          </label>
          <label>
            Longitude
            <input name="lon" type="number" step="any" required placeholder="-81.78" />
          </label>
          <button type="submit">Add unit</button>
        </form>
      </section>

      {msg && <p className="toast-inline">{msg}</p>}

      <section>
        <h2>Uplink traffic</h2>
        <table className="link-log">
          <thead>
            <tr>
              <th>Time</th>
              <th>Unit</th>
              <th>Type</th>
              <th>Size</th>
              <th>Delay</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {packets.slice(0, 50).map((p) => (
              <tr key={p.id} className={`pkt-${p.status}`} title={p.error ?? ""}>
                <td>{clock(p.accepted_at)}</td>
                <td>{p.unit_id ?? "?"}</td>
                <td>{p.typ ?? "?"}</td>
                <td>{p.bytes} B</td>
                <td>{p.delay !== null ? `${p.delay.toFixed(1)} s` : "…"}</td>
                <td>{p.error ? `${p.status}: ${p.error}` : p.status.replace("_", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
