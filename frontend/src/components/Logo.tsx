export default function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="34" height="27" viewBox="0 0 48 38" fill="none" className="shrink-0">
        <g stroke="#3b82f6" strokeWidth="2.4" strokeLinecap="round">
          <line x1="6" y1="19" x2="20" y2="8" />
          <line x1="6" y1="19" x2="20" y2="30" />
          <line x1="20" y1="8" x2="38" y2="14" />
          <line x1="20" y1="30" x2="38" y2="24" />
          <line x1="38" y1="14" x2="38" y2="24" />
        </g>
        <g fill="#fff">
          <circle cx="6" cy="19" r="3.6" />
          <circle cx="20" cy="8" r="3.6" />
          <circle cx="20" cy="30" r="3.6" />
        </g>
        <g fill="#3b82f6">
          <circle cx="38" cy="14" r="3.6" />
          <circle cx="38" cy="24" r="3.6" />
        </g>
      </svg>
      <div className="flex flex-col leading-none">
        <span className="font-display text-[15px] font-extrabold tracking-[0.14em] text-white">
          HALEY365
        </span>
        <span className="mt-[3px] text-[8px] tracking-[0.24em] text-ink-faint">
          CLIENT PORTAL
        </span>
      </div>
    </div>
  )
}
