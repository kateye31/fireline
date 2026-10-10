/** Fireline mark: a flame sitting on a horizon line. */
export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <defs>
        <linearGradient id="fl-ember" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffb347" />
          <stop offset=".5" stopColor="#ff7a2f" />
          <stop offset="1" stopColor="#ff3d2e" />
        </linearGradient>
      </defs>
      <path
        d="M12 2.5c.8 3.4 4.6 5.4 4.6 10a4.6 4.6 0 0 1-9.2 0c0-1.9.9-3.3 1.9-4.2 0 1.8.9 2.8 1.9 2.8 0-2.8-.9-5.4.8-8.6z"
        fill="url(#fl-ember)"
      />
      <path d="M3 21h18" stroke="url(#fl-ember)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function Flame({ size = 16, color = "#fff" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2.5c.8 3.4 4.6 5.4 4.6 10a4.6 4.6 0 0 1-9.2 0c0-1.9.9-3.3 1.9-4.2 0 1.8.9 2.8 1.9 2.8 0-2.8-.9-5.4.8-8.6z"
        fill={color}
      />
    </svg>
  );
}

export function Pines({ size = 44 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M16 8 8 24h5l-6 10h18l-6-10h5z" strokeLinejoin="round" />
      <path d="M33 14l-6 12h4l-5 8h14l-5-8h4z" strokeLinejoin="round" />
      <path d="M16 34v6M33 34v6M4 40h40" strokeLinecap="round" />
    </svg>
  );
}
