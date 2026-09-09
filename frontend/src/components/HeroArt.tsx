/** Decorative inline-SVG illustrations for hero sections — flat, on-brand
 * line art (not photographic, not 3D) that echoes the site's actual subject
 * matter: a sensor/gear wheel, a robotic arm placing a part, and a training
 * loss curve. Purely decorative (aria-hidden, pointer-events: none via CSS),
 * positioned behind or beside copy the way the Contact/Achievements pages'
 * reference layout does. Colors come from the existing CSS custom
 * properties so they stay in sync with the rest of the theme automatically. */

export function GearWheel({ className }: { className?: string }) {
  const spokes = Array.from({ length: 8 }, (_, i) => (i * 360) / 8);
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true">
      <circle cx="100" cy="100" r="72" stroke="var(--accent)" strokeWidth="5" fill="none" opacity="0.55" />
      <circle cx="100" cy="100" r="15" fill="var(--accent)" opacity="0.3" />
      <circle cx="100" cy="100" r="15" stroke="var(--accent-soft)" strokeWidth="2" fill="none" opacity="0.7" />
      {spokes.map((deg, i) => {
        const rad = (deg * Math.PI) / 180;
        const x1 = 100 + Math.cos(rad) * 22;
        const y1 = 100 + Math.sin(rad) * 22;
        const x2 = 100 + Math.cos(rad) * 72;
        const y2 = 100 + Math.sin(rad) * 72;
        return (
          <line key={deg} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--accent)" strokeWidth="2.5" opacity="0.4" />
        );
      })}
      {spokes.map((deg, i) => {
        const rad = (deg * Math.PI) / 180;
        const x = 100 + Math.cos(rad) * 72;
        const y = 100 + Math.sin(rad) * 72;
        return <circle key={deg} cx={x} cy={y} r="5" fill={i % 2 === 0 ? "var(--accent-soft)" : "#ec1e62"} opacity="0.85" />;
      })}
    </svg>
  );
}

export function RobotArmCar({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 260 170" className={className} aria-hidden="true">
      {/* conveyor line with dots */}
      <line x1="10" y1="150" x2="250" y2="150" stroke="var(--border)" strokeWidth="2" />
      {[30, 70, 110, 190, 230].map((x) => (
        <circle key={x} cx={x} cy="150" r="2.5" fill="var(--accent-soft)" opacity="0.6" />
      ))}
      {/* car body */}
      <rect x="130" y="118" width="90" height="26" rx="6" fill="var(--accent-soft)" opacity="0.9" />
      <path d="M148 118 L162 100 L196 100 L206 118 Z" fill="var(--accent-soft)" opacity="0.9" />
      <circle cx="150" cy="146" r="10" fill="var(--bg)" stroke="var(--accent-soft)" strokeWidth="3" />
      <circle cx="200" cy="146" r="10" fill="var(--bg)" stroke="var(--accent-soft)" strokeWidth="3" />
      {/* robot arm: base -> shoulder -> elbow -> gripper, over the car */}
      <circle cx="60" cy="150" r="9" fill="var(--accent)" opacity="0.8" />
      <line x1="60" y1="150" x2="55" y2="70" stroke="var(--accent)" strokeWidth="7" strokeLinecap="round" opacity="0.8" />
      <circle cx="55" cy="70" r="7" fill="var(--accent-soft)" />
      <line x1="55" y1="70" x2="130" y2="55" stroke="var(--accent)" strokeWidth="7" strokeLinecap="round" opacity="0.8" />
      <circle cx="130" cy="55" r="7" fill="var(--accent-soft)" />
      <line x1="130" y1="55" x2="163" y2="95" stroke="var(--accent)" strokeWidth="6" strokeLinecap="round" opacity="0.8" />
      <path d="M155 95 L163 88 L171 95 L163 104 Z" fill="#ec1e62" opacity="0.85" />
    </svg>
  );
}

export function LossChart({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 180 120" className={className} aria-hidden="true">
      <line x1="24" y1="10" x2="24" y2="96" stroke="var(--border)" strokeWidth="1.5" />
      <line x1="24" y1="96" x2="170" y2="96" stroke="var(--border)" strokeWidth="1.5" />
      <text x="10" y="14" fill="var(--muted)" fontSize="9" fontFamily="var(--mono)">LOSS</text>
      <text x="140" y="112" fill="var(--muted)" fontSize="9" fontFamily="var(--mono)">ITER</text>
      <path
        d="M26 16 C 60 24, 70 70, 100 84 S 150 92, 168 94"
        fill="none" stroke="var(--accent-soft)" strokeWidth="2.5"
      />
      <circle cx="26" cy="16" r="3.5" fill="var(--accent)" />
    </svg>
  );
}
