"use client";

/**
 * ThemeProvider
 *
 * Wrap the root layout with this component. It reads the persisted theme on
 * first mount, applies the "dark" class to <html>, and exposes the active
 * theme + toggle function via ThemeContext.
 *
 * Usage (app/layout.tsx):
 *   <ThemeProvider>
 *     {children}
 *   </ThemeProvider>
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { applyTheme, resolveInitialTheme, type Theme } from "@/lib/theme";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Start with "light" on the server; correct on the client in the effect so
  // we avoid a hydration mismatch.
  const [theme, setThemeState] = useState<Theme>("light");

  useEffect(() => {
    const initial = resolveInitialTheme();
    applyTheme(initial);
    setThemeState(initial);
  }, []);

  const setTheme = (next: Theme) => {
    applyTheme(next);
    setThemeState(next);
  };

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Internal hook — consumed by useTheme and ThemeToggle
// ---------------------------------------------------------------------------

export function useThemeContext(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useThemeContext must be used inside <ThemeProvider>");
  }
  return ctx;
}
