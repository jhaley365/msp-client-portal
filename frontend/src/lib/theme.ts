/**
 * Theme constants shared between the context, hook, and any SSR helpers.
 *
 * The chosen theme is persisted to localStorage under STORAGE_KEY so it
 * survives page reloads. The <html> element gets the class "dark" when the
 * active theme is dark, which is what Tailwind's `darkMode: "class"` reads.
 */

export type Theme = "light" | "dark";

export const STORAGE_KEY = "msp-theme";
export const DARK_CLASS = "dark";

/** Return the initial theme: stored preference → OS preference → light. */
export function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "light"; // SSR guard

  const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (stored === "light" || stored === "dark") return stored;

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/** Apply a theme to the <html> element and persist the choice. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add(DARK_CLASS);
  } else {
    root.classList.remove(DARK_CLASS);
  }
  localStorage.setItem(STORAGE_KEY, theme);
}
