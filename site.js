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

const mapButton = document.querySelector('#load-map');
if (mapButton) {
  mapButton.hidden = false;
  mapButton.addEventListener('click', () => {
    const frame = document.createElement('iframe');
    frame.src = mapButton.dataset.src;
    frame.title = 'Карта: Санкт-Петербург, улица Комиссара Смирнова, 15';
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    frame.tabIndex = 0;
    document.querySelector('#map-placeholder').replaceWith(frame);
    frame.focus();
  }, { once: true });
}
