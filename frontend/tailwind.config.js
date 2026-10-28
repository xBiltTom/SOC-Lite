/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'rgb(var(--ink) / <alpha-value>)',
        base: Object.fromEntries([950, 900, 850, 800, 700, 600].map((step) =>
          [step, `rgb(var(--base-${step}) / <alpha-value>)`],
        )),
        slate: Object.fromEntries([100, 200, 300, 400, 500, 600, 700, 800, 900].map((step) =>
          [step, `rgb(var(--slate-${step}) / <alpha-value>)`],
        )),
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          soft: 'rgb(var(--accent-soft) / <alpha-value>)',
          deep: 'rgb(var(--accent) / <alpha-value>)',
        },
        ...Object.fromEntries(['rose', 'emerald', 'amber', 'yellow', 'orange', 'sky', 'cyan', 'blue', 'violet', 'indigo'].map((color) =>
          [color, Object.fromEntries([200, 300, 400].map((shade) => [shade, `rgb(var(--status-${color}) / <alpha-value>)`]))],
        )),
        critical: '#FB7185',
        high: '#FB923C',
        medium: '#FACC15',
        low: '#38BDF8',
        info: '#94A3B8',
      },
      fontFamily: {
        sans: ['Adwaita Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['Adwaita Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 2px 6px -4px rgb(var(--ink) / 0.12)',
        glow: '0 12px 32px -16px rgb(var(--ink) / 0.2)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseRing: {
          '0%': { transform: 'scale(0.9)', opacity: '0.6' },
          '70%': { transform: 'scale(1.35)', opacity: '0' },
          '100%': { transform: 'scale(1.35)', opacity: '0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.35s ease-out both',
        'pulse-ring': 'pulseRing 3s ease-out infinite',
      },
    },
  },
  plugins: [],
}
