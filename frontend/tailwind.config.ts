import type { Config } from "tailwindcss";

const config: Config = {
  // "class" strategy: Tailwind applies dark-mode variants only when the
  // <html> element has the "dark" class. ThemeProvider manages that class.
  darkMode: "class",

  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/hooks/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],

  theme: {
    extend: {},
  },

  plugins: [],
};

export default config;
