import { startPageLoader } from "./page-loader.js";

const pageReady = startPageLoader();

// iOS Safari enables the :active state when a touch listener is registered.
document.querySelectorAll('.case-link').forEach((link) => {
  link.addEventListener('touchstart', () => {}, { passive: true });
});

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
    pageReady.then(() => {
      document.getElementById(returnTo.slice(1))?.scrollIntoView();
      sessionStorage.removeItem('portfolio-return');
    });
  }

  const scrollHint = document.querySelector('.hero-scroll');
  const dismissHint = () => {
    if (window.scrollY <= 24) return;
    scrollHint.hidden = true;
    window.removeEventListener('scroll', dismissHint);
  };

  scrollHint?.addEventListener('click', (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const target = document.querySelector(scrollHint.hash);
    if (!target) return;
    event.preventDefault();
    scrollHint.hidden = true;
    window.removeEventListener('scroll', dismissHint);

    const startY = window.scrollY;
    const endY = startY + target.getBoundingClientRect().top;
    history.pushState(null, '', scrollHint.hash);
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      window.scrollTo({ top: endY, behavior: 'instant' });
      target.focus({ preventScroll: true });
      return;
    }

    const portfolio = document.querySelector('.portfolio');
    const previousTranslate = portfolio.style.translate;
    const interruptEvents = ['wheel', 'touchstart', 'pointerdown', 'keydown'];
    const started = performance.now();
    let frame;
    const stop = () => {
      cancelAnimationFrame(frame);
      portfolio.style.translate = previousTranslate;
      interruptEvents.forEach((type) => window.removeEventListener(type, stop));
    };
    interruptEvents.forEach((type) => window.addEventListener(type, stop, { passive: true }));

    const animate = (now) => {
      const progress = Math.min(1, (now - started) / 1000);
      const eased = progress * progress * (2.70158 * progress - 1.70158);
      const position = startY + (endY - startY) * eased;
      // Render Back's anticipation even when the browser cannot scroll above 0.
      portfolio.style.translate = position < 0 ? `0 ${-position}px` : previousTranslate;
      window.scrollTo({ top: Math.max(0, position), behavior: 'instant' });
      if (progress < 1) frame = requestAnimationFrame(animate);
      else {
        stop();
        target.focus({ preventScroll: true });
      }
    };
    frame = requestAnimationFrame(animate);
  });

  pageReady.then(() => {
    // Let anchor/history restoration settle before showing a hint at the top.
    requestAnimationFrame(() => {
      if (!scrollHint || window.scrollY > 24) return;
      scrollHint.hidden = false;
      window.addEventListener('scroll', dismissHint, { passive: true });
    });
  });
}
