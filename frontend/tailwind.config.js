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
            bg: 'rgba(239, 68, 68, 0.12)',
            border: 'rgba(239, 68, 68, 0.2)',
          },
          high: {
            DEFAULT: '#f97316',
            bg: 'rgba(249, 115, 22, 0.12)',
            border: 'rgba(249, 115, 22, 0.2)',
          },
          medium: {
            DEFAULT: '#eab308',
            bg: 'rgba(234, 179, 8, 0.12)',
            border: 'rgba(234, 179, 8, 0.2)',
          },
          low: {
            DEFAULT: '#3b82f6',
            bg: 'rgba(59, 130, 246, 0.12)',
            border: 'rgba(59, 130, 246, 0.2)',
          },
          info: {
            DEFAULT: '#6b7280',
            bg: 'rgba(107, 114, 128, 0.12)',
            border: 'rgba(107, 114, 128, 0.2)',
          },
        },
        tier: {
          recon: '#3b82f6',
          hunter: '#a855f7',
          siege: '#ef4444',
        },
        glass: {
          DEFAULT: 'rgba(255, 255, 255, 0.03)',
          border: 'rgba(255, 255, 255, 0.06)',
          hover: 'rgba(255, 255, 255, 0.05)',
          active: 'rgba(255, 255, 255, 0.08)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan-line': 'scanLine 2s linear infinite',
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.3s ease-out',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'spin-slow': 'spin 3s linear infinite',
        'float': 'float 6s ease-in-out infinite',
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
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        glowPulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
      boxShadow: {
        'glow-sm': '0 0 15px rgba(239, 68, 68, 0.1)',
        'glow-md': '0 0 30px rgba(239, 68, 68, 0.15)',
        'glow-lg': '0 0 50px rgba(239, 68, 68, 0.2)',
        'inner-light': 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      },
    },
  },
  plugins: [],
};
