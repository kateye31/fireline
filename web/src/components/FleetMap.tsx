import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { LayersControl, MapContainer, Marker, TileLayer, Tooltip, useMap } from "react-leaflet";
import { Unit } from "../api";
import { STATUS_LABEL } from "../format";

// Ocala National Forest.
const DEFAULT_CENTER: [number, number] = [29.18, -81.78];

export interface Focus {
  lat: number;
  lon: number;
  key: number; // bump to re-fly to the same spot
}

function icon(u: Unit, selected: boolean) {
  const cls = ["pin", `pin-${u.status}`, u.sim ? "pin-sim" : "", selected ? "pin-selected" : ""].join(" ");
  return L.divIcon({
    className: "",
    html: `<div class="${cls}"><i></i><span>${u.id}</span></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

/** A marker that eases to its new spot when a unit is relocated (NFC tap), instead of jumping. */
function GlideMarker({
  lat,
  lon,
  icon,
  zIndexOffset,
  onClick,
  children,
}: {
  lat: number;
  lon: number;
  icon: L.DivIcon;
  zIndexOffset: number;
  onClick: () => void;
  children: ReactNode;
}) {
  const [pos, setPos] = useState<[number, number]>([lat, lon]);
  const from = useRef(pos);
  from.current = pos;

  useEffect(() => {
    const [la0, lo0] = from.current;
    if (la0 === lat && lo0 === lon) return;
    const start = performance.now();
    const ms = 1400;
    let raf = 0;
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / ms);
      const e = 1 - Math.pow(1 - k, 3); // ease-out cubic
      setPos([la0 + (lat - la0) * e, lo0 + (lon - lo0) * e]);
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [lat, lon]);

  return (
    <Marker position={pos} icon={icon} zIndexOffset={zIndexOffset} eventHandlers={{ click: onClick }}>
      {children}
    </Marker>
  );
}

function FlyTo({ focus }: { focus: Focus | null }) {
  const map = useMap();
  useEffect(() => {
    if (focus) map.flyTo([focus.lat, focus.lon], Math.max(map.getZoom(), 13), { duration: 1.2 });
  }, [focus, map]);
  return null;
}

function Resize({ visible }: { visible: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (visible) map.invalidateSize(); // Leaflet mis-sizes tiles if the map was hidden
  }, [visible, map]);
  return null;
}

function FitOnce({ units }: { units: Unit[] }) {
  const map = useMap();
  const placed = units.filter((u) => u.lat !== null && u.lon !== null);
  const ready = placed.length > 0;
  useEffect(() => {
    if (!ready) return;
    const b = L.latLngBounds(placed.map((u) => [u.lat!, u.lon!] as [number, number]));
    map.fitBounds(b.pad(0.25), { maxZoom: 12 });
  }, [ready, map]); // only the first time units appear; after that the operator owns the view
  return null;
}

export default function FleetMap({
  units,
  selected,
  focus,
  visible,
  onSelect,
}: {
  units: Unit[];
  selected: string | null;
  focus: Focus | null;
  visible: boolean;
  onSelect: (id: string) => void;
}) {
  const placed = useMemo(() => units.filter((u) => u.lat !== null && u.lon !== null), [units]);

  return (
    <MapContainer center={DEFAULT_CENTER} zoom={11} className="map" zoomControl={false}>
      <LayersControl position="topleft">
        <LayersControl.BaseLayer name="Map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer checked name="Satellite">
          <TileLayer
            attribution="Tiles &copy; Esri"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          />
        </LayersControl.BaseLayer>
      </LayersControl>
      <Resize visible={visible} />
      <FitOnce units={placed} />
      <FlyTo focus={focus} />
      {placed.map((u) => (
        <GlideMarker
          key={u.id}
          lat={u.lat!}
          lon={u.lon!}
          icon={icon(u, u.id === selected)}
          zIndexOffset={u.status === "alert" ? 1000 : 0}
          onClick={() => onSelect(u.id)}
        >
          <Tooltip direction="top" offset={[0, -10]}>
            <b>{u.name && u.name !== u.id ? `${u.id} · ${u.name}` : u.id}</b>
            {u.sim ? " (simulated)" : ""}
            <br />
            {STATUS_LABEL[u.status]}
            {u.temp !== null && ` · ${u.temp.toFixed(1)} °C`}
            {u.rh !== null && ` · ${u.rh.toFixed(0)} %`}
          </Tooltip>
        </GlideMarker>
      ))}
    </MapContainer>
  );
}
