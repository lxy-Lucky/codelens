/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0e0f11',
          secondary: '#16171b',
          tertiary: '#1c1d22',
          elevated: '#222329',
          hover: '#292a31',
        },
        border: {
          subtle: '#2e2f37',
          medium: '#3a3b44',
        },
        txt: {
          primary: '#e8e6e1',
          secondary: '#9d9a93',
          tertiary: '#6b6860',
        },
        accent: {
          DEFAULT: '#d4a574',
          dim: '#b8895c',
        },
        ok: '#7cb87c',
        warn: '#d4a574',
        err: '#c47070',
        info: '#709cc4',
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "'Fira Code'", 'monospace'],
        display: ["'DM Serif Display'", 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
