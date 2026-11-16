// Paleta "Fivox Green". La misma se usa en el CDN (app/templates/_head.html)
// y en la compilación de producción (ver README).
module.exports = {
  content: ['./app/**/*.html'],
  theme: {
    extend: {
      colors: {
        green: {
          50: '#effaf2', 100: '#d8f3df', 200: '#b3e6c2', 300: '#82d29d', 400: '#4fb87a',
          500: '#2a9d5f', 600: '#1e8049', 700: '#1a663c', 800: '#185133', 900: '#14422b', 950: '#0a2517',
        },
      },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
    },
  },
};
