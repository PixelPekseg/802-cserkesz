// ==========================================================
// Mobile navigation (hamburger menu)
// ==========================================================
const navToggle = document.getElementById('navToggle');
const mainNav = document.getElementById('mainNav');

navToggle.addEventListener('click', () => {
  const isOpen = mainNav.classList.toggle('open');
  navToggle.setAttribute('aria-expanded', String(isOpen));
});

// Close the menu when a link is clicked (mobile view)
mainNav.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    mainNav.classList.remove('open');
    navToggle.setAttribute('aria-expanded', 'false');
  });
});

// ==========================================================
// Dropdown submenu (Események → Programok, Naptár, Tábor; Pénzügyek → fee tabs, Eszközbérlés)
// On wide screens used with a mouse it opens on hover only (handled by
// the CSS), and clicking does nothing there. On phones/tablets (hamburger
// menu, touch) a click opens/closes it; a click outside or Esc closes it.
// ==========================================================
const subMenus = [...document.querySelectorAll('.has-sub')];
const hoverMenu = window.matchMedia('(hover: hover) and (min-width: 1281px)');

function closeSubMenus(except) {
  subMenus.forEach(item => {
    if (item === except) return;
    item.classList.remove('open');
    item.querySelector('.nav-sub-toggle')?.setAttribute('aria-expanded', 'false');
  });
}

subMenus.forEach(item => {
  const toggle = item.querySelector('.nav-sub-toggle');
  toggle?.addEventListener('click', () => {
    if (hoverMenu.matches) return;
    const isOpen = item.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(isOpen));
    closeSubMenus(item);
  });
});

document.addEventListener('click', event => {
  if (!event.target.closest('.has-sub')) closeSubMenus();
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeSubMenus();
});

// ==========================================================
// Current year in the footer
// ==========================================================
document.getElementById('year').textContent = new Date().getFullYear();

// ==========================================================
// Remembering dismissals (notice bar, home page "Közelgő programok" tab)
// A dismissal survives navigation within the site (and the back button), but
// after a reload, or after closing and reopening the browser tab, the item
// shows up again. This uses the tab-bound sessionStorage, which is cleared
// on reload.
// ==========================================================
const DISMISS_KEYS = ['closedNotices', 'upcomingTabClosed'];

(function resetDismissalsOnReload() {
  const navigation = performance.getEntriesByType?.('navigation')[0];
  try {
    if (navigation?.type === 'reload') DISMISS_KEYS.forEach(key => sessionStorage.removeItem(key));
  } catch (e) { /* storage not available – everything is shown */ }
})();

function readDismissed(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key)) || [];
  } catch (e) {
    return [];
  }
}

function addDismissed(key, id, keepOnly) {
  // keep only the ids of items that still exist, so the list does not grow
  const list = readDismissed(key).filter(item => !keepOnly || keepOnly.includes(item));
  if (!list.includes(id)) list.push(id);
  try { sessionStorage.setItem(key, JSON.stringify(list)); } catch (e) { /* never mind */ }
}

// ==========================================================
// Notice bar (top of every page, from the "Értesítők" sheet)
// Every .notice is hidden by default; it is shown when today falls between
// data-from and data-until (both optional, the data-until day still
// counts) and the visitor has not dismissed it (a dismissal lasts only until
// a reload / closing the browser tab, as described above).
// updateNotices(now) can be re-run with any date (for testing).
// ==========================================================
function updateNotices(now = new Date()) {
  const closed = readDismissed('closedNotices');
  document.querySelectorAll('.notice').forEach(notice => {
    const { from, until, id } = notice.dataset;
    const started = !from || now >= new Date(`${from}T00:00:00`);
    const notEnded = !until || now <= new Date(`${until}T23:59:59`);
    notice.hidden = !(started && notEnded && !closed.includes(id));
  });
}

document.querySelectorAll('.notice-close').forEach(button => {
  button.addEventListener('click', () => {
    const notice = button.closest('.notice');
    notice.hidden = true;
    const current = [...document.querySelectorAll('.notice')].map(n => n.dataset.id);
    addDismissed('closedNotices', notice.dataset.id, current);
  });
});

updateNotices();

// ==========================================================
// Images not uploaded yet (logo, portraits)
// An image with the data-optional attribute is removed if it fails to load,
// so instead of a broken image icon the monogram behind it shows
// (for people), or simply the text (for the logo).
// If the error happened before the script ran, the
// complete + naturalWidth check handles it.
// ==========================================================
document.querySelectorAll('img[data-optional]').forEach(img => {
  const removeImage = () => img.remove();
  if (img.complete && img.naturalWidth === 0) {
    removeImage();
  } else {
    img.addEventListener('error', removeImage, { once: true });
  }
});

// ==========================================================
// Programs – automatic handling of past events
// Every .news-card is "upcoming" or "past" based on its data-date (and optional
// data-end-date) attribute. Upcoming ones stay in #newsGrid in ascending date
// order; past ones (after the event day) move to the "Program Archívum"
// strip (#archiveGrid), the most recent first, where the report (.news-report)
// is shown instead of the description, if there is one (and the Facebook link
// not at all). Without past
// programs the archive strip stays hidden; without upcoming ones an empty-state
// message appears. A card without data-date always stays among the upcoming ones.
// updateNews(now) can be re-run with any date (for testing).
// ==========================================================
function isPastCard(card, now = new Date()) {
  const endDate = card.dataset.endDate || card.dataset.date;
  const eventEnd = endDate ? new Date(`${endDate}T23:59:59`) : null;
  return Boolean(eventEnd && !Number.isNaN(eventEnd.getTime()) && now > eventEnd);
}

// for a past program: the report instead of the description (if any), and no Facebook link
function applyPastState(card, isPast) {
  const report = card.querySelector('.news-report');
  const description = card.querySelector('.news-desc');
  if (report) report.hidden = !isPast;
  if (description) description.hidden = Boolean(isPast && report);
  card.querySelectorAll('.news-fb').forEach(link => { link.hidden = Boolean(isPast); });
}

function updateNews(now = new Date()) {
  const grid = document.getElementById('newsGrid') || document.getElementById('calendarSource');
  const onCalendarPage = grid?.id === 'calendarSource';   // naptar.html: hidden cards, no sorting
  const archive = onCalendarPage ? null : document.getElementById('archiveGrid');
  const archiveSection = document.getElementById('archivum');
  const emptyMessage = document.getElementById('newsEmpty');
  if (!grid) return;

  // Remember the original (HTML) order so it can be run more than once
  const cards = [...grid.querySelectorAll('.news-card'), ...(archive ? archive.querySelectorAll('.news-card') : [])];
  cards.forEach((card, index) => {
    if (!card.dataset.order) card.dataset.order = String(index);
  });
  cards.sort((a, b) => Number(a.dataset.order) - Number(b.dataset.order));

  const upcoming = [];
  const past = [];
  cards.forEach(card => {
    card.hidden = false;
    const isPast = isPastCard(card, now);
    applyPastState(card, isPast);
    if (onCalendarPage) return;
    ((isPast && archive) ? past : upcoming).push(card);
  });

  // Default contact: if a card has no "Kérdés esetén
  // keresd" line, the deputy team leader responsible for programs is used
  // (their name and address are in the grid's data-default-contact-* attributes).
  const defaultName = grid.dataset.defaultContactName;
  const defaultEmail = grid.dataset.defaultContactEmail;
  if (defaultName && defaultEmail) {
    cards.forEach(card => {
      if (card.querySelector('.news-contact')) return;
      const contact = document.createElement('p');
      contact.className = 'news-detail news-contact';
      const label = document.createElement('strong');
      label.textContent = 'Kérdés esetén keresd:';
      const link = document.createElement('a');
      link.className = 'inline-link';
      link.href = `mailto:${defaultEmail}`;
      link.textContent = defaultEmail;
      contact.append(label, document.createElement('br'), `${defaultName}, `, link);
      const after = card.querySelector('.news-gallery, .news-link');
      if (after) after.before(contact);
      else card.append(contact);
    });
  }

  const byDate = (a, b) =>
    (a.dataset.date || '9999-12-31').localeCompare(b.dataset.date || '9999-12-31') ||
    Number(a.dataset.order) - Number(b.dataset.order);
  if (onCalendarPage) return;
  upcoming.sort(byDate);
  past.sort((a, b) => byDate(b, a));   // archive: the most recent first
  upcoming.forEach(card => grid.append(card));
  past.forEach(card => archive.append(card));

  if (archiveSection) archiveSection.hidden = past.length === 0;
  if (emptyMessage) emptyMessage.hidden = upcoming.length > 0;

  document.dispatchEvent(new Event('newsupdated'));
}

updateNews();

// ==========================================================
// Home page – tab with the programs of the next 7 days
// Reads the programs from the cards of programok.html (data-date /
// data-end-date), so there is no separate data to maintain. Without upcoming
// programs, or if programok.html cannot be read (e.g. opened from a file),
// the tab does not appear. It shows the programs starting (or running) today
// and in the next 7 days. A dismissal survives navigation within the site;
// after a reload or reopening the browser tab, the tab shows up again.
// ==========================================================
async function initUpcomingTab(now = new Date()) {
  const tab = document.getElementById('upcomingTab');
  const list = document.getElementById('upcomingList');
  const closeButton = document.getElementById('upcomingClose');
  if (!tab || !list || !closeButton) return;

  if (readDismissed('upcomingTabClosed').length) return;

  const windowDays = 7;
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const windowEnd = new Date(startOfToday.getTime() + (windowDays + 1) * 24 * 60 * 60 * 1000);

  let doc;
  try {
    const response = await fetch('programok.html');
    if (!response.ok) return;
    doc = new DOMParser().parseFromString(await response.text(), 'text/html');
  } catch (e) {
    return;
  }

  const events = [...doc.querySelectorAll('.news-card[data-date]')]
    .map(card => {
      const start = new Date(`${card.dataset.date}T00:00:00`);
      const end = new Date(`${card.dataset.endDate || card.dataset.date}T23:59:59`);
      return {
        start, end,
        id: card.id,
        name: card.querySelector('h3')?.textContent.trim() ?? '',
        date: card.querySelector('.news-date')?.textContent.trim() ?? ''
      };
    })
    // not over yet, and starts within the next 7 days (or is already running)
    .filter(event => !Number.isNaN(event.start.getTime()) && event.name &&
                     event.end >= now && event.start < windowEnd)
    .sort((a, b) => a.start - b.start);

  if (events.length === 0) return;

  events.forEach(event => {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = event.id ? `programok.html#${event.id}` : 'programok.html';
    const name = document.createElement('span');
    name.className = 'upcoming-name';
    name.textContent = event.name;
    const date = document.createElement('span');
    date.className = 'upcoming-date';
    date.textContent = event.date;
    link.append(name, date);
    item.append(link);
    list.append(item);
  });

  closeButton.addEventListener('click', () => {
    tab.classList.remove('is-visible');
    addDismissed('upcomingTabClosed', 'closed');
  });

  // The tab stays below the header even when a notice bar is shown above it
  // (after the bar is scrolled away it returns to its original CSS position).
  const header = document.querySelector('.site-header');
  const placeTab = () => {
    if (header) tab.style.top = `${Math.max(90, header.getBoundingClientRect().bottom + 19)}px`;
  };
  window.addEventListener('scroll', placeTab, { passive: true });
  window.addEventListener('resize', placeTab);
  document.querySelectorAll('.notice-close').forEach(button => button.addEventListener('click', placeTab));
  placeTab();

  tab.hidden = false;
  // short delay so the slide-in is visible
  setTimeout(() => tab.classList.add('is-visible'), 300);
}

initUpcomingTab();

// ==========================================================
// Csatlakozom – automatic step-up of the troops on September 1
// From every .grade-card's data-grade (grade) and data-school-year (first
// year of the school year) attributes it computes which grade the troop is in
// right now: grade + (first year of the current school year - school-year).
// The school year starts on September 1. Grades 4–8 are shown, in order;
// for a grade without a troop a "coming soon" card appears.
// updateGrades(now) can be re-run with any date (for testing).
// ==========================================================
function updateGrades(now = new Date()) {
  const grid = document.getElementById('gradesGrid');
  if (!grid) return;

  const firstGrade = 4;
  const lastGrade = 8;
  const schoolYear = now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1;

  grid.querySelectorAll('.grade-card[data-placeholder]').forEach(card => card.remove());

  const byGrade = new Map();
  grid.querySelectorAll('.grade-card[data-grade]').forEach(card => {
    const grade = Number(card.dataset.grade) + (schoolYear - Number(card.dataset.schoolYear));
    const visible = Number.isFinite(grade) && grade >= firstGrade && grade <= lastGrade;
    card.hidden = !visible;
    if (!visible) return;
    card.querySelector('h3').textContent = `${grade}. osztály`;
    byGrade.set(grade, card);
  });

  for (let grade = firstGrade; grade <= lastGrade; grade++) {
    if (byGrade.has(grade)) continue;
    const card = document.createElement('div');
    card.className = 'grade-card';
    card.dataset.placeholder = 'true';
    const title = document.createElement('h3');
    title.textContent = `${grade}. osztály`;
    const text = document.createElement('p');
    text.className = 'grade-squad';
    text.textContent = 'Hamarosan frissítjük!';
    card.append(title, text);
    byGrade.set(grade, card);
  }

  [...byGrade.keys()].sort((a, b) => a - b).forEach(grade => grid.append(byGrade.get(grade)));
  // the card for older kids always stays at the end of the list
  grid.querySelectorAll('.grade-card-extra').forEach(card => grid.append(card));
}

updateGrades();

// ==========================================================
// Counters – they "roll up" when scrolled into view, like an odometer
// Every .stat-number's data-count attribute is the final value (the HTML
// holds it too, so it is correct without JS). The script replaces every digit
// with a vertically rolling strip of the digits 0–9; when the
// cards become visible, the strips roll to the right digit
// (stopping later and later from right to left). Runs only once.
// No animation with reduced motion enabled, or in old browsers.
// ==========================================================
function initCounters() {
  const numbers = [...document.querySelectorAll('.stat-number[data-count]')];
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (numbers.length === 0 || reduceMotion || !('IntersectionObserver' in window)) return;

  const turns = 2; // full turns the strip makes before stopping

  numbers.forEach(element => {
    const text = (Number.parseInt(element.dataset.count, 10) || 0).toLocaleString('hu-HU');
    element.setAttribute('aria-label', text);
    element.textContent = '';
    [...text].forEach(char => {
      if (!/\d/.test(char)) {
        const separator = document.createElement('span');
        separator.className = 'odo-sep';
        separator.setAttribute('aria-hidden', 'true');
        separator.textContent = char;
        element.append(separator);
        return;
      }
      const digit = document.createElement('span');
      digit.className = 'odo-digit';
      digit.setAttribute('aria-hidden', 'true');
      const strip = document.createElement('span');
      strip.className = 'odo-strip';
      strip.dataset.stop = String(turns * 10 + Number(char));
      for (let i = 0; i <= turns * 10 + 9; i++) {
        const item = document.createElement('span');
        item.textContent = String(i % 10);
        strip.append(item);
      }
      digit.append(strip);
      element.append(digit);
    });
  });

  const roll = stats => {
    stats.querySelectorAll('.stat-number').forEach(number => {
      const strips = [...number.querySelectorAll('.odo-strip')];
      strips.forEach((strip, index) => {
        // the left digits stop first, the rightmost one last
        strip.style.transitionDelay = `${index * 0.12}s`;
        strip.style.transform = `translateY(calc(-${strip.dataset.stop} * var(--odo-h)))`;
      });
    });
  };

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      roll(entry.target);
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.stats').forEach(stats => observer.observe(stats));
}

initCounters();

// ==========================================================
// Programs – stepping the card row with arrows
// 3 cards are visible at a time (2 or 1 on narrower screens); the arrows
// step by one card. If every card fits, the arrows are hidden;
// at the first/last position the matching arrow is disabled.
// ==========================================================
function initNewsCarousel(carouselId, trackId, prevId, nextId) {
  const carousel = document.getElementById(carouselId);
  const track = document.getElementById(trackId);
  const prev = document.getElementById(prevId);
  const next = document.getElementById(nextId);
  if (!carousel || !track || !prev || !next) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function step() {
    const card = track.querySelector('.news-card:not([hidden])');
    if (!card) return track.clientWidth;
    return card.getBoundingClientRect().width + (parseFloat(getComputedStyle(track).columnGap) || 0);
  }

  function updateButtons() {
    const maxScroll = track.scrollWidth - track.clientWidth;
    carousel.classList.toggle('is-static', maxScroll <= 2);
    prev.disabled = track.scrollLeft <= 2;
    next.disabled = track.scrollLeft >= maxScroll - 2;
  }

  prev.addEventListener('click', () => {
    track.scrollBy({ left: -step(), behavior: reducedMotion ? 'auto' : 'smooth' });
  });
  next.addEventListener('click', () => {
    track.scrollBy({ left: step(), behavior: reducedMotion ? 'auto' : 'smooth' });
  });
  track.addEventListener('scroll', updateButtons, { passive: true });
  window.addEventListener('resize', updateButtons);
  document.addEventListener('newsupdated', updateButtons);

  // If we arrived via a link to a specific card (e.g. from the home page tab),
  // scroll the row to that card.
  const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
  if (target && track.contains(target) && !target.hidden) {
    track.scrollLeft += target.getBoundingClientRect().left - track.getBoundingClientRect().left;
  }

  updateButtons();
}

initNewsCarousel('newsCarousel', 'newsGrid', 'newsPrev', 'newsNext');
initNewsCarousel('archiveCarousel', 'archiveGrid', 'archivePrev', 'archiveNext');

// ==========================================================
// Program images on the card: 2 images are visible at a time, the arrows on
// both sides step one image at a time (like between the program cards). Uses event
// delegation, so it also works on the (copied) cards opened in the calendar.
// ==========================================================
function updateGalleryButtons(gallery) {
  const track = gallery.querySelector('.news-gallery-track');
  const prev = gallery.querySelector('.gallery-prev');
  const next = gallery.querySelector('.gallery-next');
  if (!track || !prev || !next) return;
  const maxScroll = track.scrollWidth - track.clientWidth;
  prev.disabled = track.scrollLeft <= 2;
  next.disabled = track.scrollLeft >= maxScroll - 2;
}

document.addEventListener('click', event => {
  const button = event.target.closest('.gallery-btn');
  if (!button) return;
  const track = button.closest('.news-gallery')?.querySelector('.news-gallery-track');
  const image = track?.querySelector('img');
  if (!image) return;
  // step by image index (always to the start of an image), so fast repeated clicks do not drift
  const step = image.getBoundingClientRect().width + (parseFloat(getComputedStyle(track).columnGap) || 0);
  const current = Math.round(track.scrollLeft / step);
  const target = Math.max(0, current + (button.classList.contains('gallery-prev') ? -1 : 1));
  const left = Math.min(target * step, track.scrollWidth - track.clientWidth);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  track.scrollTo({ left, behavior: reducedMotion ? 'auto' : 'smooth' });
  // update the arrows right away for the target (do not wait for the scroll to end)
  const gallery = button.closest('.news-gallery');
  gallery.querySelector('.gallery-prev').disabled = left <= 2;
  gallery.querySelector('.gallery-next').disabled = left >= track.scrollWidth - track.clientWidth - 2;
});

// scroll events do not bubble, so we "catch" them on the document
document.addEventListener('scroll', event => {
  if (event.target.classList?.contains('news-gallery-track')) updateGalleryButtons(event.target.closest('.news-gallery'));
}, true);
window.addEventListener('resize', () => document.querySelectorAll('.news-gallery').forEach(updateGalleryButtons));
document.querySelectorAll('.news-gallery').forEach(updateGalleryButtons);

// ==========================================================
// Programs – calendar
// Builds the monthly calendar from the page's cards (data-date, optionally
// data-end-date). Past programs already hidden from the list stay in it.
// Clicking a marked day shows that day's programs below.
// ==========================================================
function initCalendar() {
  const root = document.getElementById('calendar');
  const detail = document.getElementById('calendarDetail');
  if (!root || !detail) return;

  const monthNames = ['január', 'február', 'március', 'április', 'május', 'június',
    'július', 'augusztus', 'szeptember', 'október', 'november', 'december'];
  const weekdays = ['H', 'K', 'Sze', 'Cs', 'P', 'Szo', 'V'];
  const pad = n => String(n).padStart(2, '0');
  const dayKey = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;

  const events = [...document.querySelectorAll(
    '#newsGrid .news-card[data-date], #archiveGrid .news-card[data-date], #calendarSource .news-card[data-date]')]
    .map(card => ({
      card,
      start: card.dataset.date,
      end: card.dataset.endDate || card.dataset.date,
      title: card.querySelector('h3')?.textContent.trim() ?? ''
    }))
    .filter(event => /^\d{4}-\d{2}-\d{2}$/.test(event.start));

  const eventsOn = key => events.filter(event => event.start <= key && key <= event.end);
  const element = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  };

  const today = new Date();
  const todayKey = dayKey(today.getFullYear(), today.getMonth(), today.getDate());
  let year = today.getFullYear();
  let month = today.getMonth();
  let selected = null;

  function changeMonth(delta) {
    const target = new Date(year, month + delta, 1);
    year = target.getFullYear();
    month = target.getMonth();
    selected = null;
    render();
  }

  function renderDetail() {
    detail.replaceChildren();
    const dayEvents = selected ? eventsOn(selected) : [];

    if (dayEvents.length === 0) {
      const hasAny = events.some(event =>
        event.start <= dayKey(year, month, 31) && event.end >= dayKey(year, month, 1));
      detail.append(element('p', 'calendar-hint',
        hasAny ? 'Kattints egy jelölt napra a részletekért.' : 'Ebben a hónapban nincs program.'));
      return;
    }

    const [y, m, d] = selected.split('-').map(Number);
    detail.append(element('h3', 'calendar-detail-title', `${y}. ${monthNames[m - 1]} ${d}.`));
    const cards = element('div', 'calendar-detail-cards');
    dayEvents.forEach(event => {
      const copy = event.card.cloneNode(true);
      copy.removeAttribute('id');
      copy.removeAttribute('data-order');
      copy.hidden = false;
      copy.classList.remove('news-card-past');
      copy.querySelectorAll('.news-past-label').forEach(label => label.remove());
      // restore the copy button's text (if the confirmation was showing)
      copy.querySelectorAll('.share-btn').forEach(btn => {
        btn.classList.remove('is-copied');
        const span = btn.querySelector('span');
        if (span) span.textContent = 'Üzenet másolása';
      });
      if (event.end < todayKey) {
        copy.querySelector('.news-meta')?.append(element('span', 'news-past-label', 'Elmúlt'));
      }
      cards.append(copy);
    });
    detail.append(cards);
  }

  function render() {
    root.replaceChildren();

    const head = element('div', 'calendar-head');
    const prev = element('button', 'calendar-nav', '\u2039');
    prev.type = 'button';
    prev.setAttribute('aria-label', 'Előző hónap');
    prev.addEventListener('click', () => changeMonth(-1));
    const next = element('button', 'calendar-nav', '\u203A');
    next.type = 'button';
    next.setAttribute('aria-label', 'Következő hónap');
    next.addEventListener('click', () => changeMonth(1));
    head.append(prev, element('h3', 'calendar-title', `${year}. ${monthNames[month]}`), next);

    const weekdayRow = element('div', 'calendar-weekdays');
    weekdays.forEach(name => weekdayRow.append(element('span', '', name)));

    // Always shows 6 weeks (42 days), so the calendar height does not change;
    // days of the neighbouring months show at the start/end of the month.
    const days = element('div', 'calendar-days');
    const offset = (new Date(year, month, 1).getDay() + 6) % 7; // the week starts on Monday
    for (let i = 0; i < 42; i++) {
      const date = new Date(year, month, 1 - offset + i);
      const day = date.getDate();
      const key = dayKey(date.getFullYear(), date.getMonth(), day);
      const dayEvents = eventsOn(key);
      const cell = element(dayEvents.length ? 'button' : 'div', 'cal-day');
      if (date.getMonth() !== month) cell.classList.add('other-month');
      if (key === todayKey) cell.classList.add('today');
      // the first day of the month also shows the short month name (e.g. "nov. 1"); on phones
      // it is hidden in the narrow cell (.cal-mon), only the number stays
      const num = element('span', 'cal-num');
      if (day === 1) num.append(element('span', 'cal-mon', `${monthNames[date.getMonth()].slice(0, 3)}. `));
      num.append(String(day));
      cell.append(num);

      if (dayEvents.length) {
        cell.type = 'button';
        cell.classList.add('has-event');
        if (key === selected) cell.classList.add('selected');
        cell.setAttribute('aria-label',
          `${monthNames[date.getMonth()]} ${day}., ${dayEvents.length} program: ${dayEvents.map(e => e.title).join(', ')}`);
        const chips = element('span', 'cal-chips');
        dayEvents.forEach(event => chips.append(element('span', 'cal-chip', event.title)));
        cell.append(chips);
        cell.addEventListener('click', () => {
          selected = key;
          render();
          root.querySelector('.cal-day.selected')?.focus();
        });
      }
      days.append(cell);
    }

    root.append(head, weekdayRow, days);
    renderDetail();
  }

  render();
}

initCalendar();

// ==========================================================
// Copy buttons (data-copy attribute): puts the given text on the clipboard
// and swaps the icon for a check mark for two seconds. If the browser does not
// allow clipboard access, the icon signals the error in its label, and the value
// stays selectable by hand. One shared (delegated) event handler
// does the work, so it also works with buttons created later (e.g. calendar details).
// ==========================================================
const copyTimers = new WeakMap();

async function copyToClipboard(value) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch (e) {
    // older browser / insecure context: temporary input field
    const field = document.createElement('textarea');
    field.value = value;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.append(field);
    field.select();
    let copied = false;
    try { copied = document.execCommand('copy'); } catch (err) { copied = false; }
    field.remove();
    return copied;
  }
}

document.addEventListener('click', async event => {
  const button = event.target.closest('.copy-btn[data-copy]');
  if (!button) return;

  const copied = await copyToClipboard(button.dataset.copy);
  if (!button.dataset.originalLabel) button.dataset.originalLabel = button.getAttribute('aria-label') || '';
  const label = button.dataset.copyLabel || 'Szöveg';

  clearTimeout(copyTimers.get(button));
  button.classList.toggle('is-copied', copied);
  button.setAttribute('aria-label', copied ? `${label} másolva` : 'Nem sikerült, jelöld ki kézzel');
  button.title = copied ? 'Másolva!' : 'Nem sikerült, jelöld ki kézzel';
  copyTimers.set(button, setTimeout(() => {
    button.classList.remove('is-copied');
    button.setAttribute('aria-label', button.dataset.originalLabel);
    button.title = 'Másolás';
  }, 2000));
});

// ==========================================================
// Adds a copy button next to every e-mail address (mailto link) (not in the footer or on program cards).
// Runs at the end of the page so it reaches the elements created earlier.
// ==========================================================
document.querySelectorAll('a[href^="mailto:"]').forEach(link => {
  const address = link.getAttribute('href').slice('mailto:'.length).split('?')[0];
  if (!address || link.closest('.email-copy, .site-footer, .news-card')) return;

  const wrapper = document.createElement('span');
  wrapper.className = 'email-copy';
  link.replaceWith(wrapper);
  wrapper.append(link);

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'copy-btn';
  button.dataset.copy = address;
  button.dataset.copyLabel = 'E-mail cím';
  button.setAttribute('aria-label', `${address} másolása`);
  button.title = 'Másolás';
  button.innerHTML =
    '<svg class="icon-copy" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/></svg>' +
    '<svg class="icon-check" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>';
  wrapper.append(button);
});

// ==========================================================
// Program card enlarged: clicking the card opens a pop-up. On the left
// (on top on phones) the card's texts and buttons, in the main area the
// program's images and videos in a multi-column, vertically scrolling gallery (without
// cropping); clicking an image or video opens the lightbox (the video starts there
// when its play button is clicked, in the Drive player). Links, buttons and
// paging arrows on the card work as usual; clicking a card thumbnail
// opens the pop-up at that image. Closing: ×, clicking the backdrop, Esc.
// Also works on the (copied) cards shown below the calendar.
// ==========================================================
(function initProgramModal() {
  if (!document.getElementById('newsGrid') && !document.getElementById('calendarSource')) return;
  const CARDS = '#newsGrid .news-card, #archiveGrid .news-card, #calendarDetail .news-card';

  const overlay = document.createElement('div');
  overlay.className = 'program-modal';
  overlay.hidden = true;
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.innerHTML =
    '<div class="program-modal-card">' +
    '<button class="program-modal-close" type="button" aria-label="Bezárás">&times;</button>' +
    '<article class="news-card program-modal-text"></article>' +
    '<div class="program-modal-gallery" data-gallery></div>' +
    '</div>';
  document.body.append(overlay);

  const box = overlay.querySelector('.program-modal-card');
  const text = overlay.querySelector('.program-modal-text');
  const gallery = overlay.querySelector('.program-modal-gallery');
  const closeButton = overlay.querySelector('.program-modal-close');
  let opener = null;

  function open(card, imageIndex = -1) {
    opener = card;
    // the texts and buttons (without the card's image strip); the share button works from the .news-card
    text.replaceChildren(...[...card.children]
      .filter(child => !child.classList.contains('news-gallery'))
      .map(child => child.cloneNode(true)));
    text.querySelectorAll('.share-btn').forEach(btn => {
      btn.classList.remove('is-copied');
      const span = btn.querySelector('span');
      if (span) span.textContent = 'Üzenet másolása';
    });

    const images = [...card.querySelectorAll('.news-gallery img')];
    gallery.replaceChildren(...images.map(source => {
      if (source.dataset.video) return videoTile(source);
      const img = document.createElement('img');
      img.src = source.dataset.full || source.src;   // the large version here
      img.dataset.full = source.dataset.full || source.src;
      img.alt = source.alt;
      img.loading = 'lazy';
      img.tabIndex = 0;
      img.setAttribute('role', 'button');
      img.setAttribute('aria-label', `${source.alt} (nagyítás)`);
      return img;
    }));
    box.classList.toggle('no-images', images.length === 0);

    overlay.setAttribute('aria-label', card.querySelector('h3')?.textContent.trim() ?? 'Program');
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    box.scrollTop = 0;
    text.scrollTop = 0;
    gallery.scrollTop = 0;
    if (imageIndex >= 0 && gallery.children[imageIndex]) {
      gallery.children[imageIndex].scrollIntoView({ block: 'center' });
    }
    closeButton.focus();
  }

  // Video: preview image with a play icon; on click (as with images) the lightbox opens,
  // where the Drive player can be started
  function videoTile(source) {
    const tile = document.createElement('div');
    tile.className = 'program-modal-video';
    const poster = document.createElement('img');
    poster.src = source.dataset.full || source.src;
    poster.dataset.full = poster.src;
    poster.dataset.video = source.dataset.video;
    poster.alt = source.alt;
    poster.loading = 'lazy';
    poster.tabIndex = 0;
    poster.setAttribute('role', 'button');
    poster.setAttribute('aria-label', `${source.alt} (lejátszás nagyban)`);
    tile.append(poster);
    return tile;
  }

  function close() {
    overlay.hidden = true;
    gallery.replaceChildren();
    document.body.style.overflow = '';
    opener?.focus();
  }

  document.addEventListener('click', event => {
    const card = event.target.closest(CARDS);
    if (!card || overlay.contains(card)) return;
    if (event.target.closest('a, button')) return;   // links, buttons, paging arrows
    const thumb = event.target.closest('.news-gallery img');
    const index = thumb ? [...card.querySelectorAll('.news-gallery img')].indexOf(thumb) : -1;
    open(card, index);
  });

  document.addEventListener('keydown', event => {
    if (!overlay.hidden) {
      // if the lightbox is open above it, Esc closes that
      if (event.key === 'Escape' && document.querySelector('.lightbox:not([hidden])') === null) close();
      return;
    }
    const card = event.target.closest?.(CARDS);
    if (card && event.target === card && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      open(card);
    }
  });

  closeButton.addEventListener('click', close);
  overlay.addEventListener('click', event => {
    if (event.target === overlay) close();
  });

  // cards reachable by keyboard too (the calendar copies inherit it through cloning)
  const prepare = card => {
    card.tabIndex = 0;
    card.setAttribute('aria-haspopup', 'dialog');
    card.title = 'Kattints a nagyításhoz';
  };
  document.querySelectorAll(CARDS).forEach(prepare);
})();

// ==========================================================
// Lightbox: clicking the .camp-col images shows the image at full size
// on a dark background (without a caption). Closing: × button, clicking the backdrop or Esc;
// stepping: arrows with the buttons or on the keyboard (left/right arrow).
// ==========================================================
(function initLightbox() {
  const SELECTOR = '.camp-col img, .camp-media-3 img, .side-photos img, .home-gallery img, .team-split-image img, .program-modal-gallery img, .site-gallery img';
  // on the programs page the images only appear later in the pop-up, so they are needed there too
  if (!document.querySelector(SELECTOR) && !document.querySelector('#newsGrid, #calendarSource')) return;

  const overlay = document.createElement('div');
  overlay.className = 'lightbox';
  overlay.hidden = true;
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Képnagyítás');
  overlay.innerHTML =
    '<button class="lightbox-btn lightbox-close" type="button" aria-label="Bezárás">&times;</button>' +
    '<button class="lightbox-btn lightbox-prev" type="button" aria-label="Előző kép">&#8249;</button>' +
    '<figure class="lightbox-figure"><img class="lightbox-img" alt="">' +
    '<div class="lightbox-video" hidden></div></figure>' +
    '<button class="lightbox-btn lightbox-next" type="button" aria-label="Következő kép">&#8250;</button>';
  document.body.append(overlay);

  const view = overlay.querySelector('.lightbox-img');
  const videoStage = overlay.querySelector('.lightbox-video');
  const closeButton = overlay.querySelector('.lightbox-close');
  let images = [];
  let index = 0;
  let opener = null;

  function show(i) {
    index = (i + images.length) % images.length;
    const item = images[index];
    const src = item.dataset.full || item.currentSrc || item.src;
    videoStage.replaceChildren();   // moving on stops the video that is playing
    if (item.dataset.video) {
      // video: at first only the preview and the play button; a click starts the Drive player
      // (the page only connects to Google at that point)
      view.hidden = true;
      videoStage.hidden = false;
      const poster = document.createElement('img');
      poster.src = src;
      poster.alt = item.alt;
      const play = document.createElement('button');
      play.type = 'button';
      play.className = 'lightbox-play';
      play.setAttribute('aria-label', `${item.alt} lejátszása`);
      play.addEventListener('click', () => {
        const frame = document.createElement('iframe');
        // the Drive player runs in a sandbox (it cannot navigate this page); set before src
        frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox');
        frame.src = `https://drive.google.com/file/d/${encodeURIComponent(item.dataset.video)}/preview`;
        frame.title = item.alt;
        frame.allow = 'autoplay; fullscreen';
        frame.allowFullscreen = true;
        videoStage.replaceChildren(frame);
      });
      videoStage.append(poster, play);
    } else {
      videoStage.hidden = true;
      view.hidden = false;
      // load the large version (data-full) instead of the small thumbnail
      view.src = src;
      view.alt = item.alt;
    }
  }

  function open(trigger) {
    // one program's images (data-gallery) page among themselves, the other images across the whole page;
    // the order is the order of appearance (DOM)
    const gallery = trigger.closest('[data-gallery]');
    images = gallery ? [...gallery.querySelectorAll('img')]
      : [...document.querySelectorAll(SELECTOR)].filter(img => !img.closest('[data-gallery]'));
    opener = trigger;
    show(Math.max(0, images.indexOf(trigger)));
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    closeButton.focus();
  }

  function close() {
    overlay.hidden = true;
    videoStage.replaceChildren();   // the video stops
    document.body.style.overflow = document.querySelector('.program-modal:not([hidden])') ? 'hidden' : '';
    opener?.focus();
  }

  function prepare(image) {
    image.tabIndex = 0;
    image.setAttribute('role', 'button');
    image.setAttribute('aria-label', `${image.alt} (nagyítás)`);
  }
  document.querySelectorAll(SELECTOR).forEach(prepare);

  // event delegation: images copied later (e.g. into the calendar) can be enlarged too
  document.addEventListener('click', event => {
    const image = event.target.closest?.(SELECTOR);
    if (image && !overlay.contains(image)) open(image);
  });
  document.addEventListener('keydown', event => {
    if (!overlay.hidden) {
      if (event.key === 'Escape') close();
      else if (event.key === 'ArrowLeft') show(index - 1);
      else if (event.key === 'ArrowRight') show(index + 1);
      return;
    }
    const image = event.target.closest?.(SELECTOR);
    if (image && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      open(image);
    }
  });

  closeButton.addEventListener('click', close);
  overlay.querySelector('.lightbox-prev').addEventListener('click', () => show(index - 1));
  overlay.querySelector('.lightbox-next').addEventListener('click', () => show(index + 1));
  overlay.addEventListener('click', event => {
    if (event.target === overlay) close();
  });
})();

// ==========================================================
// "Üzenet másolása" (copy message) button on programs
// Adds a button to the bottom of every .news-card with an id, which copies the
// program's short message to the clipboard, to paste it into
// WhatsApp, Messenger or anywhere. The message is built from the card:
// name, date, time, place and the program's link. The contacts'
// details are deliberately left out.
// ==========================================================
const COPY_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/>' +
  '<path d="M5 15V6a2 2 0 0 1 2-2h9"/></svg>';

function detailValue(card, label) {
  for (const paragraph of card.querySelectorAll('.news-detail')) {
    const strong = paragraph.querySelector('strong');
    if (strong && strong.textContent.trim().toLowerCase().startsWith(label)) {
      return paragraph.textContent.replace(strong.textContent, '').replace(/\s+/g, ' ').trim();
    }
  }
  return '';
}

function buildShareMessage(card, id) {
  const title = card.querySelector('h3')?.textContent.trim() ?? '';
  const date = card.querySelector('.news-date')?.textContent.trim() ?? '';
  const time = detailValue(card, 'időpont');
  const place = detailValue(card, 'helyszín');
  const url = programsUrl(id);

  const lines = [title];
  if (date) lines.push(`\u{1F4C5} ${date}`);
  if (time) lines.push(`\u{1F551} ${time}`);
  if (place) lines.push(`\u{1F4CD} ${place}`);
  lines.push(`Részletek: ${url}`);
  return lines.join('\n');
}

const CALENDAR_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/>' +
  '<path d="M3 10h18M8 3v4M16 3v4"/></svg>';

// The Google Calendar "create event" link, pre-filled (the visitor only has
// to press Save). If the card has a time (e.g. "14:00–20:00"
// or "17:45"), it becomes a timed event; otherwise an all-day one.
// With a single time (e.g. a meeting time) it creates a 1-hour event by default.
function buildCalendarLink(card) {
  const startDate = card.dataset.date;
  if (!startDate) return '';
  const endDate = card.dataset.endDate || startDate;
  const digits = value => value.replace(/-/g, '');
  const pad2 = n => String(n).padStart(2, '0');

  const times = [...detailValue(card, 'időpont').matchAll(/(\d{1,2}):(\d{2})/g)]
    .map(match => Number(match[1]) * 60 + Number(match[2]));

  let dates;
  if (times.length === 0) {
    // all-day: the end day is exclusive, so the next day
    const [y, m, d] = endDate.split('-').map(Number);
    const next = new Date(y, m - 1, d + 1);
    const nextKey = `${next.getFullYear()}${pad2(next.getMonth() + 1)}${pad2(next.getDate())}`;
    dates = `${digits(startDate)}/${nextKey}`;
  } else {
    const stamp = (day, minutes) => `${digits(day)}T${pad2(Math.floor(minutes / 60) % 24)}${pad2(minutes % 60)}00`;
    const start = times[0];
    let end = times.length > 1 ? times[1] : start + 60;
    let endDay = endDate;
    if (times.length > 1 && endDate === startDate && end < start) {
      const [y, m, d] = startDate.split('-').map(Number);
      const next = new Date(y, m - 1, d + 1);
      endDay = `${next.getFullYear()}-${pad2(next.getMonth() + 1)}-${pad2(next.getDate())}`;
    }
    if (end >= 24 * 60) {
      const [y, m, d] = endDay.split('-').map(Number);
      const next = new Date(y, m - 1, d + 1);
      endDay = `${next.getFullYear()}-${pad2(next.getMonth() + 1)}-${pad2(next.getDate())}`;
      end -= 24 * 60;
    }
    dates = `${stamp(startDate, start)}/${stamp(endDay, end)}`;
  }

  const title = card.querySelector('h3')?.textContent.trim() ?? '';
  const place = detailValue(card, 'helyszín');
  const description = (card.querySelector('.news-desc p') || card.querySelector(':scope > p:not(.news-detail)'))
    ?.textContent.replace(/\s+/g, ' ').trim() ?? '';
  const url = programsUrl(card.id);

  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: title,
    dates,
    ctz: 'Europe/Budapest',
    details: `${description}\n\nRészletek: ${url}`.trim()
  });
  if (place) params.set('location', place);
  return `https://calendar.google.com/calendar/render?${params}`;
}

const programsUrl = id => `${location.origin}${location.pathname.replace(/[^/]*$/, '')}programok.html#${id}`;

document.querySelectorAll('#newsGrid .news-card[id], #calendarSource .news-card[id]').forEach(card => {
  if (card.closest('#calendarSource') && isPastCard(card)) return;   // not needed for a past program
  const actions = document.createElement('div');
  actions.className = 'news-actions';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'share-btn';
  button.dataset.shareId = card.id;
  button.innerHTML = `${COPY_ICON}<span>Üzenet másolása</span>`;
  actions.append(button);

  const calendarLink = buildCalendarLink(card);
  if (calendarLink) {
    const calendarButton = document.createElement('a');
    calendarButton.className = 'calendar-btn';
    calendarButton.href = calendarLink;
    calendarButton.target = '_blank';
    calendarButton.rel = 'noopener noreferrer';
    calendarButton.innerHTML = `${CALENDAR_ICON}<span>Google Naptárba</span>`;
    actions.append(calendarButton);
  }
  card.append(actions);
});

document.addEventListener('click', async event => {
  const button = event.target.closest('.share-btn');
  if (!button) return;

  const card = button.closest('.news-card');
  const copied = await copyToClipboard(buildShareMessage(card, button.dataset.shareId));
  const label = button.querySelector('span');
  label.textContent = copied ? 'Másolva \u2713' : 'Nem sikerült másolni';
  button.classList.toggle('is-copied', copied);
  clearTimeout(copyTimers.get(button));
  copyTimers.set(button, setTimeout(() => {
    label.textContent = 'Üzenet másolása';
    button.classList.remove('is-copied');
  }, 2000));
});

// ==========================================================
// People's introduction pop-up
// Clicking a .person-card.has-bio card opens a pop-up with the person's
// photo, name, role, introduction and copyable e-mail address(es).
// The content comes from the hidden .person-bio block inside the card. Closing: × button,
// clicking the backdrop or Esc. Clicking links/buttons on the card does not open it.
// ==========================================================
(function initPersonModals() {
  const cards = [...document.querySelectorAll('.person-card.has-bio')];
  if (cards.length === 0) return;

  const overlay = document.createElement('div');
  overlay.className = 'person-modal';
  overlay.hidden = true;
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.innerHTML =
    '<div class="person-modal-card">' +
    '<button class="person-modal-close" type="button" aria-label="Bezárás">&times;</button>' +
    '<div class="person-modal-head"></div>' +
    '<div class="person-modal-body"></div>' +
    '</div>';
  document.body.append(overlay);

  const head = overlay.querySelector('.person-modal-head');
  const body = overlay.querySelector('.person-modal-body');
  const closeButton = overlay.querySelector('.person-modal-close');
  let opener = null;

  function open(card) {
    opener = card;
    const name = card.querySelector('h3')?.textContent.trim() ?? '';
    const bio = card.querySelector('.person-bio');
    const role = bio?.querySelector('.person-bio-role')?.textContent.trim()
      || card.querySelector('.person-role')?.textContent.trim() || '';

    head.replaceChildren();
    const photo = card.querySelector('.person-photo')?.cloneNode(true);
    if (photo) head.append(photo);
    const title = document.createElement('h3');
    title.textContent = name;
    const roleLine = document.createElement('p');
    roleLine.className = 'person-modal-role';
    roleLine.textContent = role;
    head.append(title, roleLine);

    body.replaceChildren();
    bio?.childNodes.forEach(node => {
      if (node.nodeType === 1 && node.classList.contains('person-bio-role')) return; // the role is in the header
      body.append(node.cloneNode(true));
    });

    overlay.setAttribute('aria-label', `${name} bemutatkozása`);
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    closeButton.focus();
  }

  function close() {
    overlay.hidden = true;
    document.body.style.overflow = '';
    opener?.focus();
  }

  cards.forEach(card => {
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-haspopup', 'dialog');
    card.title = 'Kattints a bemutatkozásért';
    card.addEventListener('click', event => {
      if (event.target.closest('a, button')) return;
      open(card);
    });
    card.addEventListener('keydown', event => {
      if (event.target !== card) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open(card);
      }
    });
  });

  closeButton.addEventListener('click', close);
  overlay.addEventListener('click', event => {
    if (event.target === overlay) close();
  });
  document.addEventListener('keydown', event => {
    if (!overlay.hidden && event.key === 'Escape') close();
  });
})();

// ==========================================================
// Rólunk / Csapatotthonunk: alternating "text + photos" blocks (as on the Tábor page)
// The script pairs the photos of the .side-photos block with the text sections (h3 headings): it
// splits the text into parts of even length and puts 2-3 photos next to each as a collage
// (.camp-block / .camp-media / .camp-col, the same style as on the Tábor page). The blocks
// alternate the images between left and right; on phones the images sit above the text.
// ==========================================================
(function initSplitBlocks() {
  document.querySelectorAll('.has-side-photos').forEach(section => {
    const holder = section.querySelector('.side-photos');
    const text = section.querySelector('.prose, .home-story');
    if (!holder || !text) return;
    const images = [...holder.querySelectorAll('img')];
    if (images.length === 0) return;

    // text sections: from each h3 to the next h3 (the source line stays at the end)
    const groups = [];
    let current = null;
    let firstHeading = null;
    for (const el of [...text.children]) {
      if (el.matches('.prose-source')) break;
      if (el.matches('h3')) {
        current = [];
        groups.push(current);
        firstHeading = firstHeading || el;
      }
      if (current) current.push(el);
    }
    if (groups.length === 0) return;

    const weight = group => group.reduce((sum, el) => sum + el.textContent.length, 0);
    const blockCount = Math.max(1, Math.min(groups.length, Math.floor(images.length / 2), Math.round(images.length / 2.5)));
    const total = groups.reduce((sum, group) => sum + weight(group), 0);

    const chunks = [];
    let chunk = [];
    if (groups.some(group => group[0].classList.contains('block-start'))) {
      // manual breaks: a new block starts at a heading with the .block-start class
      groups.forEach(group => {
        if (group[0].classList.contains('block-start') && chunk.length) {
          chunks.push(chunk);
          chunk = [];
        }
        chunk.push(group);
      });
    } else {
      // split the sections into contiguous parts of roughly equal length
      let acc = 0;
      groups.forEach((group, i) => {
        chunk.push(group);
        acc += weight(group);
        const remaining = groups.length - i - 1;
        const needed = blockCount - chunks.length - 1;
        if ((chunks.length < blockCount - 1) && (acc >= (total / blockCount) * (chunks.length + 1) || remaining === needed)) {
          chunks.push(chunk);
          chunk = [];
        }
      });
    }
    if (chunk.length) chunks.push(chunk);

    const base = Math.floor(images.length / chunks.length);
    const extra = images.length % chunks.length;
    const fragment = document.createDocumentFragment();
    // place of the blocks: a marker put before the first heading (the heading itself moves into the text box)
    const marker = document.createComment('');
    firstHeading.before(marker);
    let imageIndex = 0;

    chunks.forEach((groupsInChunk, index) => {
      const size = base + (index < extra ? 1 : 0);
      const blockImages = images.slice(imageIndex, imageIndex + size);
      imageIndex += size;

      const block = document.createElement('div');
      block.className = 'camp-block' + (index % 2 === 1 ? ' camp-block-reverse' : '');
      const media = document.createElement('div');
      media.className = 'camp-media';
      if (index % 2 === 1) media.style.cssText = '--col1:54%;--col2:56%;--overlap:-10%';

      if (blockImages.length === 3) {
        // 3 images: one staggered column, slightly overlapping (not two columns)
        media.classList.add('camp-media-3');
        blockImages.forEach(img => media.append(img));
      } else {
        // columns: the first column gets fewer or the same number of images, the second the rest
        const firstCount = Math.floor(blockImages.length / 2) || blockImages.length;
        [blockImages.slice(0, firstCount), blockImages.slice(firstCount)].forEach(list => {
          if (list.length === 0) return;
          const col = document.createElement('div');
          col.className = 'camp-col';
          list.forEach(img => col.append(img));
          media.append(col);
        });
      }

      const textBox = document.createElement('div');
      textBox.className = 'camp-text';
      groupsInChunk.flat().forEach(el => textBox.append(el));
      block.append(media, textBox);
      fragment.append(block);
    });

    marker.replaceWith(fragment);
    holder.remove();
    (text.classList.contains('prose') ? text : text.closest('.container') || text).classList.add('split-layout');
  });
})();

// ==========================================================
// Pénzügyek page: tabs (Tagdíj / Nagytábordíj / Kcs tábordíj) and time window
// There is no tab bar (the owner's request): the tab opens from the #tagdij / #nagytabor /
// #kcstabor hash, i.e. from the Pénzügyek dropdown in the menu; without a hash, Tagdíj.
// Period: a tab's (.fee-panel) content is shown between its data-from / data-until days
// (the end day still counts; without data-until there is no end); outside that,
// or without data-from, the .fee-empty default message. The content is written from the
// Google Sheet by tools/sync_fees.py. Test in the console:
// updateFees(new Date('2026-03-15T10:00:00'))
// ==========================================================
function updateFees(now = new Date()) {
  document.querySelectorAll('.fee-panel').forEach(panel => {
    const { from, until } = panel.dataset;
    const active = Boolean(from) && now >= new Date(`${from}T00:00:00`) &&
      (!until || now <= new Date(`${until}T23:59:59`));
    const content = panel.querySelector('.fee-content');
    const empty = panel.querySelector('.fee-empty');
    if (content) content.hidden = !active;
    if (empty) empty.hidden = active;
  });
  // Support request: at 23:59 on the day AFTER the deadline the form disappears (and is removed
  // from the page, so it cannot be reached), and the "deadline passed" message takes its place.
  document.querySelectorAll('.fee-form[data-until]').forEach(form => {
    const closed = now >= feeFormCloseTime(form);
    const open = form.querySelector('.fee-form-open');
    const message = form.querySelector('.fee-form-closed');
    if (open) open.hidden = closed;
    if (message) message.hidden = !closed;
    if (closed) form.querySelectorAll('iframe').forEach(frame => frame.remove());
  });
}

// 23:59 on the day after the deadline
function feeFormCloseTime(form) {
  const close = new Date(`${form.dataset.until}T23:59:00`);
  close.setDate(close.getDate() + 1);
  return close;
}

// if the page stays open, it updates itself at the moment of closing
(function scheduleFeeFormClose() {
  const ends = [...document.querySelectorAll('.fee-form[data-until]')]
    .map(form => feeFormCloseTime(form).getTime())
    .filter(time => time > Date.now());
  if (ends.length === 0) return;
  const wait = Math.min(...ends) - Date.now() + 500;
  if (wait < 2 ** 31) setTimeout(() => { updateFees(); scheduleFeeFormClose(); }, wait);
})();

// Contact of the Kcs tábordíj (cub camp fee) tab: of the Rajok sheet's cards only the one of the troop
// that is in 4th grade now is shown (the same calculation as on the Csatlakozom page). Returns true if
// there is such a troop; if not, the finance deputy stays the contact on the tab.
function updateCubCampContact(now = new Date()) {
  const schoolYear = now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1;
  let found = false;
  document.querySelectorAll('.fee-troop-contact [data-school-year]').forEach(card => {
    const grade = Number(card.dataset.grade) + (schoolYear - Number(card.dataset.schoolYear));
    card.hidden = grade !== 4;
    if (!card.hidden) found = true;
  });
  return found;
}

(function initFeeTabs() {
  const panels = [...document.querySelectorAll('.fee-panel[data-tab]')];
  if (panels.length === 0) return;
  const names = panels.map(panel => panel.dataset.tab);
  const menuLinks = [...document.querySelectorAll('#subFinance a')];
  const banner = document.querySelector('.page-banner h1');
  const baseTitle = document.title;

  function select(name) {
    if (!names.includes(name)) name = names[0];
    // the title banner shows the tab's name (Tagdíj / Nagytábordíj / Kcs tábordíj), not "Pénzügyek"
    const label = panels.find(panel => panel.dataset.tab === name).dataset.label;
    if (banner && label) banner.textContent = label;
    if (label) document.title = `${label} – ${baseTitle}`;
    // contact at the bottom of the tab; on the Kcs tab the 4th-grade troop, or the finance deputy if there is none
    const contactFor = name === 'kcstabor' && !updateCubCampContact() ? 'tagdij' : name;
    document.querySelectorAll('.fee-contact[data-for]').forEach(contact => {
      contact.hidden = !contact.dataset.for.split(' ').includes(contactFor);
    });
    panels.forEach(panel => {
      panel.hidden = panel.dataset.tab !== name;
      // the embedded (Google) form only loads when its tab is visible
      if (!panel.hidden) panel.querySelectorAll('.fee-form-open:not([hidden]) iframe[data-src]').forEach(frame => {
        // only a Google Form may be embedded here (the address comes from a sheet)
        if (frame.dataset.src.startsWith('https://docs.google.com/forms/')) frame.src = frame.dataset.src;
        frame.removeAttribute('data-src');
      });
    });
    menuLinks.forEach(link => {
      if (link.hash === `#${name}`) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }

  window.addEventListener('hashchange', () => select(location.hash.slice(1)));
  updateFees();   // first the periods and the expired forms, so an expired form never loads
  select(location.hash.slice(1));
})();
