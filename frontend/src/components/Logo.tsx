export default function Logo() {
  return (
    <div className="flex flex-col items-center gap-0.5">
      {/* Brand mark — 28px as spec'd for the rail header */}
      <img
        src="/haley365-mark-dark.svg"
        alt="Haley365"
        width={28}
        height={28}
        className="shrink-0"
        onError={(e) => {
          // Fallback inline mark if asset not yet deployed
          const t = e.currentTarget
          t.style.display = 'none'
          const sibling = t.nextElementSibling as HTMLElement | null
          if (sibling) sibling.style.display = 'block'
        }}
      />
      {/* Inline fallback — hidden unless img fails */}
      <svg
        width="28" height="28" viewBox="0 0 48 48" fill="none"
        style={{ display: 'none' }}
        aria-hidden="true"
      >
        <g transform="rotate(-28 24 24)">
          <ellipse cx="24" cy="24" rx="18" ry="8.5" stroke="#3b82f6" strokeWidth="2.2" fill="none" />
          <circle cx="42" cy="24" r="3.2" fill="#3b82f6" />
        </g>
        <circle cx="24" cy="24" r="4.4" fill="#fff" />
      </svg>
      {/* Two-line mono wordmark below mark */}
      <div className="text-center font-mono text-[10px] font-semibold leading-[1.1] tracking-[0.05em] text-ink-primary">
        <div>HALEY</div>
        <div>365</div>
      </div>
    </div>
  )
}
