"use client";

/**
 * useTheme — convenience hook for reading and changing the active theme.
 *
 * Must be called inside a component tree wrapped by <ThemeProvider>.
 *
 * @example
 *   const { theme, toggleTheme } = useTheme();
 *   // theme === "light" | "dark"
 */

export { useThemeContext as useTheme } from "@/components/ThemeProvider";
