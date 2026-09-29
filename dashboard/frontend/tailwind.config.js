/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg:       'var(--color-bg)',
        surface:  'var(--color-surface)',
        border:   'var(--color-border)',
        accent:   'var(--color-accent)',
        muted:    'var(--color-text-muted)',
      },
    },
  },
  plugins: [],
}
