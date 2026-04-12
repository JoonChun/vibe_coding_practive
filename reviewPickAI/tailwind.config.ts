import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx,html}'],
  theme: {
    extend: {
      colors: {
        // Core brand
        primary: '#0051FF',
        'primary-dark': '#003DC7',
        'primary-container': '#0051FF',
        negative: '#F04452',
        tertiary: '#9F0023',
        positive: '#0EA5E9',
        secondary: '#545F6E',

        // Surface hierarchy (Blue Horizon design system)
        bg: '#F8F9FB',
        surface: '#FFFFFF',
        'surface-bright': '#F8F9FB',
        'surface-container-lowest': '#FFFFFF',
        'surface-container-low': '#F2F4F6',
        'surface-container': '#ECEEF0',
        'surface-container-high': '#E6E8EA',
        'surface-container-highest': '#E0E3E5',

        // On-surface tokens
        'on-surface': '#191C1E',
        'on-surface-variant': '#434656',

        // Border
        'outline-variant': '#C3C5D9',
        outline: '#737688',

        // Text (kept for backward compat)
        text: {
          primary: '#191C1E',
          secondary: '#545F6E',
          disabled: '#ADB5BD',
        },
      },
      borderRadius: {
        DEFAULT: '16px',
        sm: '8px',
        lg: '24px',
        xl: '32px',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Pretendard"',
          '"Noto Sans KR"',
          'sans-serif',
        ],
        headline: ['"Plus Jakarta Sans"', 'sans-serif'],
        body: ['Inter', '"Noto Sans KR"', 'sans-serif'],
      },
      boxShadow: {
        whisper: '0 12px 32px -4px rgba(25, 28, 30, 0.06)',
        'whisper-sm': '0 4px 16px -2px rgba(25, 28, 30, 0.04)',
      },
    },
  },
  plugins: [],
} satisfies Config;
