/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        severity: {
          critical: {
            DEFAULT: '#ef4444',
            bg: 'rgba(239, 68, 68, 0.15)',
            border: 'rgba(239, 68, 68, 0.3)',
          },
          high: {
            DEFAULT: '#f97316',
            bg: 'rgba(249, 115, 22, 0.15)',
            border: 'rgba(249, 115, 22, 0.3)',
          },
          medium: {
            DEFAULT: '#eab308',
            bg: 'rgba(234, 179, 8, 0.15)',
            border: 'rgba(234, 179, 8, 0.3)',
          },
          low: {
            DEFAULT: '#3b82f6',
            bg: 'rgba(59, 130, 246, 0.15)',
            border: 'rgba(59, 130, 246, 0.3)',
          },
          info: {
            DEFAULT: '#6b7280',
            bg: 'rgba(107, 114, 128, 0.15)',
            border: 'rgba(107, 114, 128, 0.3)',
          },
        },
        tier: {
          recon: '#3b82f6',
          hunter: '#a855f7',
          siege: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan-line': 'scanLine 2s linear infinite',
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        scanLine: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
