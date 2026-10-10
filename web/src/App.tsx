import { useEffect, useMemo, useRef, useState } from "react";
import { Incident } from "./api";
import { useFleet } from "./useFleet";
import FleetMap, { Focus } from "./components/FleetMap";
import UnitList from "./components/UnitList";
import UnitDetail from "./components/UnitDetail";
import AlertFeed from "./components/AlertFeed";
import SettingsPage from "./components/SettingsPage";

type Tab = "map" | "alerts" | "settings";

let audio: AudioContext | null = null;

/** Two-tone alarm chirp; needs one user click first to unlock audio. */
function chirp() {
  if (!audio) return;
  const t = audio.currentTime;
  [880, 660, 880].forEach((f, i) => {
    const o = audio!.createOscillator();
    const g = audio!.createGain();
    o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t + i * 0.18);
    g.gain.exponentialRampToValueAtTime(0.25, t + i * 0.18 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.18 + 0.16);
    o.connect(g).connect(audio!.destination);
    o.start(t + i * 0.18);
    o.stop(t + i * 0.18 + 0.17);
  });
}

export default function App() {
  const fleet = useFleet();
  const [tab, setTab] = useState<Tab>("map");
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [toast, setToast] = useState<Incident | null>(null);
  const [alertsOn, setAlertsOn] = useState(false);
  const toastTimer = useRef<number>();

  const units = useMemo(() => Object.values(fleet.units), [fleet.units]);
  const incidents = useMemo(() => Object.values(fleet.incidents), [fleet.incidents]);
  const openCount = incidents.filter((i) => i.status === "new").length;
  const lastPacket = fleet.packets[0];

  const showUnit = (id: string) => {
    const u = fleet.units[id];
    setTab("map");
    setSelected(id);
    if (u?.lat != null && u?.lon != null) setFocus({ lat: u.lat, lon: u.lon, key: Date.now() });
  };

  // The moment judges should see: sound, notification, and the map flies to the unit.
  const showUnitRef = useRef(showUnit);
  showUnitRef.current = showUnit;
  useEffect(
    () =>
      fleet.subscribe((m) => {
        if (m.type !== "incident" || !m.data.is_new) return;
        const inc = m.data;
        chirp();
        if ("Notification" in window && Notification.permission === "granted") {
          new Notification(`Smoke detected by ${inc.unit_id}`, { body: inc.summary ?? "", tag: `inc-${inc.id}` });
        }
        setToast(inc);
        window.clearTimeout(toastTimer.current);
        toastTimer.current = window.setTimeout(() => setToast(null), 12000);
        showUnitRef.current(inc.unit_id);
        if (inc.lat != null && inc.lon != null) setFocus({ lat: inc.lat, lon: inc.lon, key: Date.now() });
      }),
    [fleet],
  );

  const enableAlerts = async () => {
    audio = audio ?? new AudioContext();
    await audio.resume();
    if ("Notification" in window && Notification.permission === "default") await Notification.requestPermission();
    setAlertsOn(true);
    chirp();
  };

  const selectedUnit = selected ? fleet.units[selected] : undefined;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo">▲</span> Fireline
        </div>
        <nav>
          <button className={tab === "map" ? "on" : ""} onClick={() => setTab("map")}>
            Fleet map
          </button>
          <button className={tab === "alerts" ? "on" : ""} onClick={() => setTab("alerts")}>
            Alerts {openCount > 0 && <span className="badge">{openCount}</span>}
          </button>
          <button className={tab === "settings" ? "on" : ""} onClick={() => setTab("settings")}>
            Settings
          </button>
        </nav>
        <div className="top-right">
          {lastPacket && (
            <span className={`uplink pkt-${lastPacket.status}`} title="Most recent satellite uplink">
              ↑ {lastPacket.unit_id ?? "?"} {lastPacket.bytes} B
              {lastPacket.delay !== null ? ` · ${lastPacket.delay.toFixed(1)} s` : " · in flight"}
            </span>
          )}
          {!alertsOn && (
            <button className="link" onClick={enableAlerts}>
              Enable alert sound
            </button>
          )}
          <span className={`live ${fleet.connected ? "on" : ""}`}>{fleet.connected ? "Live" : "Reconnecting"}</span>
        </div>
      </header>

      {toast && (
        <div className="toast" role="alert" onClick={() => setTab("alerts")}>
          <b>🔥 Smoke detected by {toast.unit_id}</b>
          <span>{toast.summary}</span>
        </div>
      )}

      <main className={`main main-${tab}`}>
        <section className="map-wrap" hidden={tab !== "map"}>
          <FleetMap units={units} selected={selected} focus={focus} visible={tab === "map"} onSelect={showUnit} />
          <aside className="panel">
            {selectedUnit ? (
              <UnitDetail unit={selectedUnit} fleet={fleet} onBack={() => setSelected(null)} />
            ) : (
              <UnitList units={units} onSelect={showUnit} />
            )}
          </aside>
        </section>
        {tab === "alerts" && (
          <AlertFeed incidents={incidents} units={fleet.units} settings={fleet.settings} onShowUnit={showUnit} />
        )}
        {tab === "settings" && <SettingsPage settings={fleet.settings} packets={fleet.packets} />}
      </main>
    </div>
  );
}
