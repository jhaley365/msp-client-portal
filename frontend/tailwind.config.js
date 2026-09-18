/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        page:   'var(--color-page)',
        chrome: 'var(--color-chrome)',
        panel:  'var(--color-panel)',
        rail:   'var(--color-rail)',
        'panel-border':  'var(--color-panel-border)',
        'divider':       'var(--color-divider)',
        'row-hairline':  'var(--color-row-hairline)',
        'ctrl-bg':       'var(--color-ctrl-bg)',
        'ctrl-border':   'var(--color-ctrl-border)',
        'rail-active':   'var(--color-rail-active)',
        accent:      '#2f6bff',
        'icon-blue': '#7cb0ff',
        ink: {
          primary:   'var(--color-ink-primary)',
          secondary: 'var(--color-ink-secondary)',
          muted:     'var(--color-ink-muted)',
          label:     'var(--color-ink-label)',
          faint:     'var(--color-ink-faint)',
          mono:      'var(--color-ink-mono)',
          chevron:   'var(--color-ink-chevron)',
        },
        tone: {
          ok:        '#4ade80',
          'ok-bg':   'rgba(74,222,128,0.12)',
          warn:      '#fbbf24',
          'warn-bg': 'rgba(251,191,36,0.13)',
          crit:      '#f87171',
          'crit-bg': 'rgba(248,113,113,0.13)',
          info:      '#7cb0ff',
          'info-bg': 'rgba(124,176,255,0.13)',
          purple:    '#c4b5fd',
          'purple-bg':'rgba(196,181,253,0.13)',
          muted:     '#9aa6b8',
          'muted-bg':'rgba(154,166,184,0.12)',
        },
      },
      fontFamily: {
        /* display alias removed — IBM Plex Sans is the one sans */
        sans:    ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono:    ['"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
