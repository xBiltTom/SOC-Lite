try {
  document.documentElement.dataset.theme = localStorage.getItem('soclite.theme.v1') === 'dark' ? 'dark' : 'light';
} catch {
  document.documentElement.dataset.theme = 'light';
}
