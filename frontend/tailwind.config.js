/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: 'rgba(var(--background), <alpha-value>)',
        foreground: 'rgba(var(--foreground), <alpha-value>)',
        primary: {
          DEFAULT: 'rgba(var(--primary), <alpha-value>)',
          hover: 'rgba(var(--primary-hover), <alpha-value>)',
        },
        card: 'rgba(var(--card), <alpha-value>)',
        border: 'rgba(var(--border), <alpha-value>)',
      },
    },
  },
  plugins: [],
}
