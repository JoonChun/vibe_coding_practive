/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design system tokens
        'primary': '#6c2f00',
        'primary-container': '#8b4513',
        'primary-fixed': '#ffdbc9',
        'primary-fixed-dim': '#ffb68c',
        'on-primary': '#ffffff',
        'on-primary-fixed': '#321200',
        'on-primary-fixed-variant': '#753401',
        'secondary': '#006e16',
        'on-secondary': '#ffffff',
        'tertiary': '#394156',
        'on-tertiary': '#ffffff',
        'surface': '#fbf9f5',
        'background': '#fbf9f5',
        'surface-container-lowest': '#ffffff',
        'surface-container-low': '#f5f3ef',
        'surface-container': '#efeeea',
        'surface-container-high': '#eae8e4',
        'surface-container-highest': '#e4e2de',
        'on-surface': '#1b1c1a',
        'on-background': '#1b1c1a',
        'on-surface-variant': '#54433a',
        'outline': '#877369',
        'outline-variant': '#dac2b6',
        'error': '#ba1a1a',
        // Legacy theme tokens (keep for backward compat)
        theme: {
          light: { bg: '#fbf9f5', accent: '#6c2f00' },
          dark: { bg: '#0F172A', accent: '#00FF41' }
        }
      },
      fontFamily: {
        headline: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        body: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['"Plus Jakarta Sans"', 'Pretendard', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        label: ['"Space Grotesk"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
        '4xl': '2rem',
        '5xl': '2.5rem',
      },
      boxShadow: {
        'fur': '0 8px 24px -4px rgba(139, 69, 19, 0.08)',
        'fur-lg': '0 16px 48px -8px rgba(139, 69, 19, 0.12)',
      }
    },
  },
  plugins: [],
}
