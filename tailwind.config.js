/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './static/**/*.{html,js}',
  ],
  safelist: [
    // These are built via template literals in index.html (the day-type picker):
    //   `bg-${opt.c}-600`  and  `border-${opt.c}-600`  where opt.c ∈ green|blue|gray
    // The scanner can't see dynamically constructed class names, so list them explicitly.
    'bg-green-600', 'border-green-600',
    'bg-blue-600',  'border-blue-600',
    'bg-gray-600',  'border-gray-600',
  ],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#f97316', light: '#fed7aa', dark: '#c2410c' },
      },
    },
  },
  plugins: [],
}
