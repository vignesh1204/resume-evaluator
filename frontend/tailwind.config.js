/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 12px 40px rgba(0,0,0,0.25)",
      },
    },
  },
  plugins: [],
};
