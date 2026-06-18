/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
            color: '#374151',
            pre: { backgroundColor: '#1f2937', color: '#f9fafb' },
          },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
