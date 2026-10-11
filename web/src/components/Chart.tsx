/** Small dependency-free line chart for heartbeat history. */
export default function Chart({
  points,
  color,
  label,
  unit,
  guides = [],
  domain,
}: {
  points: { t: number; v: number }[];
  color: string;
  label: string;
  unit: string;
  guides?: { v: number; label: string }[];
  domain?: [number, number];
}) {
  const W = 320;
  const H = 90;
  const pad = { l: 28, r: 6, t: 8, b: 14 };
  const last = points[points.length - 1];

  if (points.length < 2) {
    return (
      <div className="chart">
        <div className="chart-head">
          <span>{label}</span>
          <b>{last ? `${last.v.toFixed(1)}${unit}` : "–"}</b>
        </div>
        <div className="chart-empty">Waiting for heartbeats…</div>
      </div>
    );
  }

  const vs = points.map((p) => p.v).concat(guides.map((g) => g.v));
  let [lo, hi] = domain ?? [Math.min(...vs), Math.max(...vs)];
  if (hi - lo < 1) [lo, hi] = [lo - 1, hi + 1];
  const t0 = points[0].t;
  const t1 = last.t === t0 ? t0 + 1 : last.t;
  const x = (t: number) => pad.l + ((t - t0) / (t1 - t0)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const d = points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
  const area = `${d}L${x(last.t).toFixed(1)},${H - pad.b}L${x(t0).toFixed(1)},${H - pad.b}Z`;
  const gid = `fill-${label.replace(/\W/g, "")}`;
  const minutes = Math.round((t1 - t0) / 60);

  return (
    <div className="chart">
      <div className="chart-head">
        <span>{label}</span>
        <b style={{ color }}>
          {last.v.toFixed(1)}
          {unit}
        </b>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label} over the last ${minutes} minutes`}>
        <text x={pad.l - 4} y={pad.t + 4} className="axis" textAnchor="end">
          {hi.toFixed(0)}
        </text>
        <text x={pad.l - 4} y={H - pad.b} className="axis" textAnchor="end">
          {lo.toFixed(0)}
        </text>
        {guides.map((g) => (
          <g key={g.v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(g.v)} y2={y(g.v)} className="guide" />
            <text x={W - pad.r} y={y(g.v) - 2} className="axis" textAnchor="end">
              {g.label}
            </text>
          </g>
        ))}
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity={0.28} />
            <stop offset="1" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#${gid})`} />
        <path d={d} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(last.t)} cy={y(last.v)} r={6} fill={color} opacity={0.2} />
        <circle cx={x(last.t)} cy={y(last.v)} r={3} fill={color} />
        <text x={pad.l} y={H - 2} className="axis">
          {minutes > 0 ? `${minutes} min` : "now"}
        </text>
      </svg>
    </div>
  );
}
