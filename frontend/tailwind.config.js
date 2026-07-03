/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        page: '#0c111e',
        chrome: '#0a0f1a',
        panel: '#0e1424',
        accent: '#2f6bff',
        'brand-light': '#60a5fa',
        'icon-blue': '#7cb0ff',
        ink: {
          primary: '#eaf0fb',
          secondary: '#c4cede',
          muted: '#8a97ab',
          faint: '#7f8ea3',
        },
        tone: {
          ok: '#4ade80',
          'ok-bg': 'rgba(74,222,128,0.12)',
          warn: '#fbbf24',
          'warn-bg': 'rgba(251,191,36,0.14)',
          crit: '#f87171',
          'crit-bg': 'rgba(248,113,113,0.14)',
          info: '#7cb0ff',
          'info-bg': 'rgba(124,176,255,0.14)',
          purple: '#c4b5fd',
          'purple-bg': 'rgba(196,181,253,0.14)',
          muted: '#9aa6b8',
          'muted-bg': 'rgba(154,166,184,0.12)',
        },
      },
      fontFamily: {
        display: ['Archivo', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
