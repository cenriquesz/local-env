export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        'gh-bg': '#0d1117',
        'gh-card': '#161b22',
        'gh-border': '#30363d',
        'gh-text': '#e6edf3',
        'gh-muted': '#8b949e',
        'gh-green': '#3fb950',
        'gh-yellow': '#d29922',
        'gh-red': '#f85149',
        'gh-blue': '#58a6ff',
        'gh-orange': '#e05c3a',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      }
    }
  },
  plugins: []
}
