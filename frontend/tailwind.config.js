/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#060a0f',
        surface: '#0d1520',
        border: '#1a2a3a',
        'accent-green': '#00ff88',
        'accent-red': '#ff3366',
        'accent-gold': '#ffd700',
        'accent-blue': '#00aaff',
        'text-dim': '#5a7a9a',
      },
      fontFamily: {
        mono: ['"Space Mono"', 'monospace'],
        display: ['"Bebas Neue"', 'sans-serif'],
        sans: ['"Noto Sans"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
