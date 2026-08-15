export default function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="34" height="34" viewBox="0 0 48 48" fill="none" className="shrink-0">
        <g transform="rotate(-28 24 24)">
          <ellipse cx="24" cy="24" rx="18" ry="8.5" stroke="#3b82f6" strokeWidth="2.2" fill="none" />
          <circle cx="42" cy="24" r="3.2" fill="#3b82f6" />
        </g>
        <circle cx="24" cy="24" r="4.4" fill="#fff" />
      </svg>
      <div className="flex flex-col leading-none">
        <span className="font-display text-[15px] font-extrabold tracking-[0.14em] text-ink-primary">
          HALEY365
        </span>
        <span className="mt-[3px] text-[8px] tracking-[0.24em] text-ink-faint">
          CLIENT PORTAL
        </span>
      </div>
    </div>
  )
}
