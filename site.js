const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#navigation');
const narrowScreen = window.matchMedia('(max-width: 640px)');

function closeMenu(returnFocus = false) {
  menuButton.setAttribute('aria-expanded', 'false');
  navigation.hidden = narrowScreen.matches;
  if (returnFocus) menuButton.focus();
}

if (menuButton && navigation) {
  menuButton.hidden = false;
  closeMenu();
  menuButton.addEventListener('click', () => {
    const expanded = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!expanded));
    navigation.hidden = expanded;
  });
  navigation.addEventListener('click', (event) => {
    if (event.target.closest('a')) closeMenu();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') {
      closeMenu(true);
    }
  });
  narrowScreen.addEventListener('change', () => closeMenu());
}


(() => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (!reducedMotion.matches && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('reveal-visible');
          observer.unobserve(entry.target);
        }
      }
    }, { threshold: .05 });
    document.querySelectorAll('.about-copy, .about-photo, .contact-card, .map-panel').forEach((element) => {
      element.classList.add('reveal-pending');
      observer.observe(element);
    });
    document.addEventListener('focusin', (event) => {
      const element = event.target.closest('.reveal-pending');
      if (element) { element.classList.add('reveal-visible'); observer.unobserve(element); }
    });
    reducedMotion.addEventListener('change', () => {
      if (reducedMotion.matches) {
        observer.disconnect();
        document.querySelectorAll('.reveal-pending').forEach(e => e.classList.add('reveal-visible'));
      }
    });
  }
  const progress = document.querySelector('.reading-progress');
  const topButton = document.querySelector('.scroll-top');
  if (topButton) topButton.hidden = false;
  const sections = [...document.querySelectorAll('main > section')];
  const navLinks = [...document.querySelectorAll('#navigation a')];
  let pending = false;
  function update() {
    pending = false;
    const offset = window.scrollY;
    const maximum = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    if (progress) {
      progress.hidden = maximum === 0;
      progress.firstElementChild.style.transform = `scaleX(${maximum ? Math.min(1, offset / maximum) : 0})`;
    }
    const current = sections.filter(e => e.getBoundingClientRect().top <= window.innerHeight * .35).at(-1);
    let target = null;
    if (current?.id === 'sec-69fc') target = '#sec-69fc';
    else if (current?.id === 'sec-a2cb') target = '#sec-a2cb';
    else if (current && current.id !== 'sec-44bd') target = '#sec-6db2';
    navLinks.forEach(link => {
      if (link.getAttribute('href') === target) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }
  function schedule() { if (!pending) { pending = true; requestAnimationFrame(update); } }
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule, { passive: true });
  window.addEventListener('stak:analytics-consent', schedule);
  topButton?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: reducedMotion.matches ? 'auto' : 'smooth' });
    document.querySelector('.brand')?.focus({ preventScroll: true });
  });
  schedule();
})();
