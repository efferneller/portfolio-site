// Standard links preserve browser navigation, including direct links to cases.
// Restore the project position when returning to the portfolio from a case.
document.querySelectorAll('.case-back').forEach((link) => {
  link.addEventListener('click', () => {
    sessionStorage.setItem('portfolio-return', link.hash);
  });
});

if (document.body.classList.contains('home-page')) {
  const returnTo = sessionStorage.getItem('portfolio-return');
  if (returnTo && location.hash === returnTo) {
    document.fonts.ready.then(() => {
      document.getElementById(returnTo.slice(1))?.scrollIntoView();
      sessionStorage.removeItem('portfolio-return');
    });
  }
}
