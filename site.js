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

// Preference collection only. Analytics counters will be connected separately.
(() => {
  const banner = document.querySelector('#consent-banner');
  const openButton = document.querySelector('#consent-open');
  if (!banner || !openButton) return;
  const storageKey = 'stak.analytics-consent.v2';
  const maxAge = 180 * 24 * 60 * 60 * 1000;
  let saved = null;
  try {
    const value = JSON.parse(localStorage.getItem(storageKey));
    if (value?.version === 2 && typeof value.allowed === 'boolean'
      && Number.isFinite(value.savedAt) && Date.now() >= value.savedAt
      && Date.now() - value.savedAt < maxAge) saved = value;
  } catch { /* Default to no analytics when browser storage is unavailable. */ }

  function announce() {
    const consent = Object.freeze({ allowed: saved?.allowed === true });
    window.stakAnalyticsConsent = consent;
    window.dispatchEvent(new CustomEvent('stak:analytics-consent', { detail: consent }));
  }
  function save(allowed) {
    saved = { version: 2, allowed, savedAt: Date.now() };
    try { localStorage.setItem(storageKey, JSON.stringify(saved)); } catch { /* Current visit still works. */ }
    banner.hidden = true;
    announce();
  }
  banner.hidden = saved !== null;
  openButton.hidden = false;
  document.querySelector('#consent-accept').addEventListener('click', () => save(true));
  document.querySelector('#consent-reject').addEventListener('click', () => save(false));
  openButton.addEventListener('click', () => {
    banner.hidden = false;
    document.querySelector('#consent-accept').focus({ preventScroll: true });
    window.dispatchEvent(new CustomEvent('stak:analytics-consent', { detail: window.stakAnalyticsConsent }));
  });
  announce();
})();

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
    document.querySelectorAll('.service-card:not(.reveal-from-left):not(.reveal-from-right), .about-copy, .about-photo, .contact-card, .map-panel').forEach((element) => {
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
  const header = document.querySelector('.site-header');
  const slidingCards = [...document.querySelectorAll('.reveal-from-left, .reveal-from-right')].map(element => {
    element.classList.add('reveal-scroll');
    return { element, direction: element.classList.contains('reveal-from-left') ? -1 : 1, progress: null };
  });
  const progress = document.querySelector('.reading-progress');
  const topButton = document.querySelector('.scroll-top');
  const sections = [...document.querySelectorAll('main > section')];
  const navLinks = [...document.querySelectorAll('#navigation a')];
  let pending = false;
  function update() {
    pending = false;
    const offset = window.scrollY;
    if (header) {
      if (offset > 100) header.classList.add('is-compact');
      else if (offset < 20) header.classList.remove('is-compact');
    }
    // Use each card's vertical position, so long mobile cards stay readable.
    // The same progress runs backwards when the scroll direction changes.
    const viewportTop = header?.getBoundingClientRect().bottom ?? 0;
    const revealDistance = Math.min(160, Math.max(1, (window.innerHeight - viewportTop) * .2));
    for (const card of slidingCards) {
      const bounds = card.element.getBoundingClientRect();
      const amount = reducedMotion.matches ? 1 : Math.max(0, Math.min(1,
        (window.innerHeight - bounds.top) / revealDistance,
        (bounds.bottom - viewportTop) / revealDistance));
      const progress = Number((amount * amount * (3 - 2 * amount)).toFixed(3));
      if (progress !== card.progress) {
        card.element.style.setProperty('--reveal-progress', progress);
        card.element.style.setProperty('--reveal-shift', `${card.direction * 64 * (1 - progress)}px`);
        card.progress = progress;
      }
    }
    const maximum = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    if (progress) {
      progress.hidden = maximum === 0;
      progress.firstElementChild.style.transform = `scaleX(${maximum ? Math.min(1, offset / maximum) : 0})`;
    }
    if (topButton) topButton.hidden = offset < 700 || !document.querySelector('#consent-banner').hidden;
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
  reducedMotion.addEventListener('change', schedule);
  window.addEventListener('stak:analytics-consent', schedule);
  topButton?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: reducedMotion.matches ? 'auto' : 'smooth' });
    document.querySelector('.brand')?.focus({ preventScroll: true });
  });
  schedule();
})();
