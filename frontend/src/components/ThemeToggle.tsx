"use client";

/**
 * ThemeToggle
 *
 * An accessible icon button that switches between light and dark mode.
 * Drop it anywhere in a header or toolbar — it has no layout opinions of
 * its own (no margins/position). Size it with the optional `className` prop.
 *
 * @example
 *   // In a navbar:
 *   <ThemeToggle className="ml-auto" />
 *
 *   // Larger hit area:
 *   <ThemeToggle className="p-3" />
 */

import { useTheme } from "@/hooks/useTheme";

interface ThemeToggleProps {
  /** Extra Tailwind classes forwarded to the <button> wrapper. */
  className?: string;
}

export function ThemeToggle({ className = "" }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
      className={[
        // Base layout
        "inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5",
        "text-sm font-medium select-none",
        // Light-mode colours
        "bg-gray-100 text-gray-700 hover:bg-gray-200",
        // Dark-mode colours (requires darkMode: 'class' in tailwind.config)
        "dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600",
        // Transition
        "transition-colors duration-200 focus-visible:outline-none",
        "focus-visible:ring-2 focus-visible:ring-offset-2",
        "focus-visible:ring-blue-500 dark:focus-visible:ring-offset-gray-900",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
      <span className="sr-only md:not-sr-only">
        {isDark ? "Light" : "Dark"}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Inline SVG icons — no external icon library required
// ---------------------------------------------------------------------------

function SunIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
      <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
      <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
      <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}
