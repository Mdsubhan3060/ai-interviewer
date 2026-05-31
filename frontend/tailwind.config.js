// frontend/tailwind.config.js
// ============================================
// Tailwind CSS Configuration
// ============================================
// content: tells Tailwind which files to scan for class names.
// If a class isn't used in these files, Tailwind removes it from
// the final CSS bundle (keeps your CSS tiny in production).
// ============================================

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      // Custom color palette for the app
      colors: {
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',  // Primary brand color
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        success: {
          light: '#dcfce7',
          DEFAULT: '#16a34a',
          dark: '#14532d',
        },
        danger: {
          light: '#fee2e2',
          DEFAULT: '#dc2626',
          dark: '#7f1d1d',
        },
        warning: {
          light: '#fef9c3',
          DEFAULT: '#ca8a04',
          dark: '#713f12',
        },
      },
      // Custom font sizes
      fontSize: {
        'display': ['3.5rem', { lineHeight: '1.1', fontWeight: '700' }],
      },
      // Animation for loading states
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-subtle': 'bounce 2s infinite',
      },
      // Custom box shadows for cards
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'card-hover': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
      },
    },
  },
  plugins: [],
}
