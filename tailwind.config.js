module.exports = {
  content: [
    './home/templates/**/*.html',
    './partners/templates/**/*.html',
    './courier/templates/**/*.html',
    './static/js/**/*.js'
  ],
  theme: {
    extend: {
      colors: {
        'brand-blue': '#1e3a5f',
        'brand-blue-dark': '#152a45',
        'brand-orange': '#ff6b35',
        'brand-orange-dark': '#e55a2b',
        'brand-green': '#25d366'
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif']
      }
    }
  },
  plugins: []
};
