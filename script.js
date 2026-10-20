// ==========================================================
// Mobil navigáció (hamburger menü)
// ==========================================================
const navToggle = document.getElementById('navToggle');
const mainNav = document.getElementById('mainNav');

navToggle.addEventListener('click', () => {
  const isOpen = mainNav.classList.toggle('open');
  navToggle.setAttribute('aria-expanded', String(isOpen));
});

// Menü bezárása, ha egy linkre kattintunk (mobil nézetben)
mainNav.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    mainNav.classList.remove('open');
    navToggle.setAttribute('aria-expanded', 'false');
  });
});

// ==========================================================
// Lenyíló almenü (Programok → Naptár, Tábor)
// Egérrel használt széles képernyőn csak rámutatásra nyílik (ezt a CSS
// intézi), ott a kattintás nem csinál semmit. Telefonon/tableten (hamburger
// menü, érintés) kattintásra nyílik/csukódik; kívül kattintás vagy Esc bezárja.
// ==========================================================
const subMenus = [...document.querySelectorAll('.has-sub')];
const hoverMenu = window.matchMedia('(hover: hover) and (min-width: 1381px)');

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
// Aktuális év a láblécben
// ==========================================================
document.getElementById('year').textContent = new Date().getFullYear();

// ==========================================================
// Bezárások megjegyzése (értesítősáv, főoldali "Közelgő programok" fül)
// A bezárás az oldalon belüli lapozás (és a vissza gomb) alatt megmarad, de
// újratöltéskor, illetve a böngészőlap bezárása és újbóli megnyitása után az
// elem újra megjelenik. Ehhez a böngészőlaphoz kötött sessionStorage-ot
// használjuk, és újratöltéskor kiürítjük.
// ==========================================================
const DISMISS_KEYS = ['closedNotices', 'upcomingTabClosed'];

(function resetDismissalsOnReload() {
  const navigation = performance.getEntriesByType?.('navigation')[0];
  try {
    localStorage.removeItem('closedNotices');   // a korábbi, tartós megjegyzés maradványa
    if (navigation?.type === 'reload') DISMISS_KEYS.forEach(key => sessionStorage.removeItem(key));
  } catch (e) { /* a tárolás nem elérhető – minden megjelenik */ }
})();

function readDismissed(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key)) || [];
  } catch (e) {
    return [];
  }
}

function addDismissed(key, id, keepOnly) {
  // csak a még létező elemek azonosítóit tartjuk meg, hogy a lista ne nőjön
  const list = readDismissed(key).filter(item => !keepOnly || keepOnly.includes(item));
  if (!list.includes(id)) list.push(id);
  try { sessionStorage.setItem(key, JSON.stringify(list)); } catch (e) { /* nem baj */ }
}

// ==========================================================
// Értesítősáv (minden oldal tetején, a Táblázat "Értesítők" lapjából)
// Minden .notice alapból rejtett; akkor látszik, ha a mai nap a
// data-from és data-until közé esik (mindkettő opcionális, a data-until
// napja még beleszámít), és a látogató nem zárta be (a bezárás a fenti
// szabály szerint csak újratöltésig / a böngészőlap bezárásáig érvényes).
// Az updateNotices(now) tetszőleges időponttal újrafuttatható (tesztelés).
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
// Még nem feltöltött képek (logó, személyek fotói) kezelése
// A data-optional attribútumú képet eltávolítjuk, ha nem töltődik be,
// így nem törött kép ikon látszik, hanem a mögötte lévő monogram
// (személyeknél), illetve egyszerűen csak a szöveg (logónál).
// Ha a hiba még azelőtt megtörtént, hogy a szkript lefutott, a
// complete + naturalWidth ellenőrzés kezeli le.
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
// Programok – a lejárt események automatikus kezelése
// Minden .news-card a data-date (és opcionálisan data-end-date) attribútuma
// alapján "közelgő" vagy "lejárt". A közelgők a #newsGrid-ben maradnak dátum
// szerint növekvő sorrendben; a lejártak (az esemény napja után) átkerülnek a
// "Program Archívum" sávba (#archiveGrid), a legfrissebb elöl, és ott a leírás
// helyett a beszámoló (.news-report) látszik, ha van (a Facebook-link pedig
// egyáltalán nem). Ha nincs lejárt
// program, az archívum sáv rejtve marad; ha nincs közelgő, üres-állapot üzenet
// jelenik meg. A data-date nélküli hír mindig a közelgők között marad.
// Az updateNews(now) tetszőleges időponttal újrafuttatható (tesztelés).
// ==========================================================
function isPastCard(card, now = new Date()) {
  const endDate = card.dataset.endDate || card.dataset.date;
  const eventEnd = endDate ? new Date(`${endDate}T23:59:59`) : null;
  return Boolean(eventEnd && !Number.isNaN(eventEnd.getTime()) && now > eventEnd);
}

// lejárt programnál a leírás helyett a beszámoló (ha van), és nincs Facebook-link
function applyPastState(card, isPast) {
  const report = card.querySelector('.news-report');
  const description = card.querySelector('.news-desc');
  if (report) report.hidden = !isPast;
  if (description) description.hidden = Boolean(isPast && report);
  card.querySelectorAll('.news-fb').forEach(link => { link.hidden = Boolean(isPast); });
}

function updateNews(now = new Date()) {
  const grid = document.getElementById('newsGrid') || document.getElementById('calendarSource');
  const onCalendarPage = grid?.id === 'calendarSource';   // naptar.html: rejtett kártyák, nincs rendezés
  const archive = onCalendarPage ? null : document.getElementById('archiveGrid');
  const archiveSection = document.getElementById('archivum');
  const emptyMessage = document.getElementById('newsEmpty');
  if (!grid) return;

  // Az eredeti (HTML-beli) sorrendet megjegyezzük, hogy többször is lefuttatható legyen
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

  // Alapértelmezett kapcsolattartó: ha egy hírnél nincs megadva "Kérdés esetén
  // keresd" sor, a programokért felelős csapatparancsnok-helyettes kerül oda
  // (neve és címe a rács data-default-contact-* attribútumaiban van).
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
  past.sort((a, b) => byDate(b, a));   // archívum: a legutóbbi elöl
  upcoming.forEach(card => grid.append(card));
  past.forEach(card => archive.append(card));

  if (archiveSection) archiveSection.hidden = past.length === 0;
  if (emptyMessage) emptyMessage.hidden = upcoming.length > 0;

  document.dispatchEvent(new Event('newsupdated'));
}

updateNews();

// ==========================================================
// Főoldal – a következő 7 nap programjainak füle
// A programokat az programok.html hírdobozaiból olvassa ki (data-date /
// data-end-date), így nincs külön adatot karbantartani. Ha nincs közelgő
// program, vagy az programok.html nem olvasható (pl. fájlból megnyitva),
// a fül nem jelenik meg. A ma és a következő 7 napban kezdődő (vagy épp tartó)
// programokat mutatja. A bezárás az oldalon belüli lapozás alatt megmarad,
// újratöltéskor vagy a böngészőlap újbóli megnyitásakor a fül újra megjelenik.
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
    // még nem ért véget, és a következő 7 napon belül kezdődik (vagy már tart)
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

  // A fül a fejléc alatt marad akkor is, ha fölötte értesítősáv látszik
  // (a sáv elgörgetése után visszaáll az eredeti, CSS-beli helyére).
  const header = document.querySelector('.site-header');
  const placeTab = () => {
    if (header) tab.style.top = `${Math.max(90, header.getBoundingClientRect().bottom + 19)}px`;
  };
  window.addEventListener('scroll', placeTab, { passive: true });
  window.addEventListener('resize', placeTab);
  document.querySelectorAll('.notice-close').forEach(button => button.addEventListener('click', placeTab));
  placeTab();

  tab.hidden = false;
  // rövid késleltetés, hogy a becsúszás látszódjon
  setTimeout(() => tab.classList.add('is-visible'), 300);
}

initUpcomingTab();

// ==========================================================
// Csatlakozom – a rajok automatikus léptetése szeptember 1-jén
// Minden .grade-card data-grade (osztály) és data-school-year (a tanév
// kezdő éve) attribútuma alapján kiszámolja, hogy a raj az adott pillanatban
// hányadik osztályba jár: grade + (aktuális tanév kezdő éve - school-year).
// A tanév szeptember 1-jén kezdődik. A 4–8. osztály látszik, sorrendben;
// ha egy osztályhoz nincs raj, "hamarosan" kártya jelenik meg.
// Az updateGrades(now) tetszőleges időponttal újrafuttatható (tesztelés).
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
  // az idősebbeknek szóló kártya mindig a lista végén marad
  grid.querySelectorAll('.grade-card-extra').forEach(card => grid.append(card));
}

updateGrades();

// ==========================================================
// Számlálók – odagörgetéskor "feltekerődnek", mint egy kilométeróra
// Minden .stat-number data-count attribútuma a végső érték (a HTML-ben
// is ez áll, így JS nélkül is helyes). A szkript minden számjegyet egy
// 0–9 számokat tartalmazó, függőlegesen gördülő szalagra cserél; ha a
// kártyák láthatóvá válnak, a szalagok a helyes számjegyig tekerednek
// (jobbról balra egyre később állnak meg). Csak egyszer fut le.
// Csökkentett mozgás beállításnál, illetve régi böngészőben nincs animáció.
// ==========================================================
function initCounters() {
  const numbers = [...document.querySelectorAll('.stat-number[data-count]')];
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (numbers.length === 0 || reduceMotion || !('IntersectionObserver' in window)) return;

  const turns = 2; // ennyi teljes kört tesz meg a szalag a megállás előtt

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
        // a bal oldali számjegyek állnak meg előbb, a jobb szélső utoljára
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
// Programok – a kártyasor léptetése nyilakkal
// Egyszerre 3 kártya látszik (keskenyebb képernyőn 2, illetve 1); a nyilak
// egy kártyányit lépnek. Ha minden kártya elfér, a nyilak elrejtődnek,
// az első/utolsó helyen a megfelelő nyíl inaktív.
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

  // Ha egy konkrét hírre mutató linkkel érkeztünk (pl. a főoldali fülről),
  // a sort arra a kártyára léptetjük.
  const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
  if (target && track.contains(target) && !target.hidden) {
    track.scrollLeft += target.getBoundingClientRect().left - track.getBoundingClientRect().left;
  }

  updateButtons();
}

initNewsCarousel('newsCarousel', 'newsGrid', 'newsPrev', 'newsNext');
initNewsCarousel('archiveCarousel', 'archiveGrid', 'archivePrev', 'archiveNext');

// ==========================================================
// Programképek a kártyán: egyszerre 2 kép látszik, a két oldali nyíllal
// képenként lehet lépni (mint a programkártyák között). Eseménydelegálással
// működik, így a naptárban megnyitott (másolt) kártyákon is.
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
  // képindex szerint lépünk (mindig egy kép elejére), így a gyors egymás utáni kattintás sem csúszik el
  const step = image.getBoundingClientRect().width + (parseFloat(getComputedStyle(track).columnGap) || 0);
  const current = Math.round(track.scrollLeft / step);
  const target = Math.max(0, current + (button.classList.contains('gallery-prev') ? -1 : 1));
  const left = Math.min(target * step, track.scrollWidth - track.clientWidth);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  track.scrollTo({ left, behavior: reducedMotion ? 'auto' : 'smooth' });
  // a nyilak állapota azonnal a cél szerint (nem várjuk meg a görgetés végét)
  const gallery = button.closest('.news-gallery');
  gallery.querySelector('.gallery-prev').disabled = left <= 2;
  gallery.querySelector('.gallery-next').disabled = left >= track.scrollWidth - track.clientWidth - 2;
});

// a görgetés nem buborékol, ezért a dokumentumon "elkapva" figyeljük
document.addEventListener('scroll', event => {
  if (event.target.classList?.contains('news-gallery-track')) updateGalleryButtons(event.target.closest('.news-gallery'));
}, true);
window.addEventListener('resize', () => document.querySelectorAll('.news-gallery').forEach(updateGalleryButtons));
document.querySelectorAll('.news-gallery').forEach(updateGalleryButtons);

// ==========================================================
// Programok – naptár
// A lap kártyáiból (data-date, opcionálisan data-end-date) építi fel a
// havi naptárat. A lejárt, a listából már elrejtett programok is benne
// maradnak. A jelölt napra kattintva a nap programjai jelennek meg alatta.
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
      // a másolás gomb szövegét visszaállítjuk (ha éppen a visszajelzés látszott)
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

    // Mindig 6 hetet mutat (42 nap), így a naptár magassága nem változik;
    // a hónap elején/végén a szomszédos hónapok napjai is látszanak.
    const days = element('div', 'calendar-days');
    const offset = (new Date(year, month, 1).getDay() + 6) % 7; // hétfővel kezdődik a hét
    for (let i = 0; i < 42; i++) {
      const date = new Date(year, month, 1 - offset + i);
      const day = date.getDate();
      const key = dayKey(date.getFullYear(), date.getMonth(), day);
      const dayEvents = eventsOn(key);
      const cell = element(dayEvents.length ? 'button' : 'div', 'cal-day');
      if (date.getMonth() !== month) cell.classList.add('other-month');
      if (key === todayKey) cell.classList.add('today');
      // a hónap első napja mellett a hónap rövid neve is látszik (pl. "nov. 1"); telefonon a
      // keskeny cellában ez elrejtődik (.cal-mon), ott csak a szám áll
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
// Másolás gombok (data-copy attribútum): a megadott szöveget a vágólapra
// teszi, és két másodpercre pipára cseréli az ikont. Ha a böngésző nem
// engedi a vágólap használatát, az ikon a hibát jelzi a címkében, az érték
// pedig kézzel kijelölhető marad. Egy közös (delegált) eseménykezelő
// dolgozik, így a később létrehozott gombokkal (pl. a naptár részletei) is működik.
// ==========================================================
const copyTimers = new WeakMap();

async function copyToClipboard(value) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch (e) {
    // régebbi böngésző / nem biztonságos környezet: ideiglenes beviteli mező
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
// Minden e-mail cím (mailto link) mellé másolás gombot tesz (a láblécben és a programok kártyáin nem).
// Az oldal végén fut, hogy a korábban létrehozott elemeket is elérje.
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
// Programkártya nagyítva: a kártyára kattintva felugró ablak nyílik. Bal
// oldalt (telefonon felül) a kártya szövegei és gombjai, a fő helyen a
// program képei és videói több oszlopos, fel-le görgethető galériában (vágás
// nélkül); a képre vagy videóra kattintva a nagyító nyílik (a videó ott,
// a lejátszás gombra kattintva indul a Drive lejátszójával). A kártyán lévő linkek, gombok és
// lapozónyilak a megszokott módon működnek; a kártya bélyegképére kattintva
// az ablak annál a képnél nyílik meg. Bezárás: ×, háttérre kattintás, Esc.
// A naptár alatt megjelenő (másolt) kártyákon is működik.
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
    // a szövegek és gombok (a kártya képsávja nélkül); a megosztás gomb a .news-card-ból dolgozik
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
      img.src = source.dataset.full || source.src;   // itt a nagy változat
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

  // Videó: előnézeti kép lejátszás ikonnal; kattintásra (mint a képeknél) a nagyító nyílik,
  // ott indítható a Drive lejátszója
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
    if (event.target.closest('a, button')) return;   // linkek, gombok, lapozónyilak
    const thumb = event.target.closest('.news-gallery img');
    const index = thumb ? [...card.querySelectorAll('.news-gallery img')].indexOf(thumb) : -1;
    open(card, index);
  });

  document.addEventListener('keydown', event => {
    if (!overlay.hidden) {
      // ha fölötte a nagyító is nyitva van, az Esc azt zárja be
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

  // billentyűzettel is elérhető kártyák (a naptár másolatai a klónozással öröklik)
  const prepare = card => {
    card.tabIndex = 0;
    card.setAttribute('aria-haspopup', 'dialog');
    card.title = 'Kattints a nagyításhoz';
  };
  document.querySelectorAll(CARDS).forEach(prepare);
})();

// ==========================================================
// Nagyítás (lightbox): a .camp-col képekre kattintva a kép teljes méretben,
// sötét háttéren jelenik meg (felirat nélkül). Bezárás: × gomb, háttérre kattintás vagy Esc;
// léptetés: nyilak a gombokkal vagy a billentyűzeten (bal/jobb nyíl).
// ==========================================================
(function initLightbox() {
  const SELECTOR = '.camp-col img, .camp-media-3 img, .side-photos img, .home-gallery img, .team-split-image img, .program-modal-gallery img, .site-gallery img';
  // a programok oldalán a képek csak a felugró ablakban jelennek meg később, ezért ott is kell
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
    videoStage.replaceChildren();   // a továbblapozás leállítja az épp futó videót
    if (item.dataset.video) {
      // videó: előbb csak az előnézet és a lejátszás gomb; kattintásra indul a Drive lejátszója
      // (a Google-höz csak ekkor kapcsolódik az oldal)
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
      // a kis bélyegkép helyett a nagy változatot töltjük be (data-full)
      view.src = src;
      view.alt = item.alt;
    }
  }

  function open(trigger) {
    // egy program képei (data-gallery) egymás között lapozhatók, a többi kép az egész oldalon;
    // a sorrend a megjelenés (DOM) szerinti
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
    videoStage.replaceChildren();   // a videó leáll
    document.body.style.overflow = document.querySelector('.program-modal:not([hidden])') ? 'hidden' : '';
    opener?.focus();
  }

  function prepare(image) {
    image.tabIndex = 0;
    image.setAttribute('role', 'button');
    image.setAttribute('aria-label', `${image.alt} (nagyítás)`);
  }
  document.querySelectorAll(SELECTOR).forEach(prepare);

  // eseménydelegálás: a később (pl. a naptárban) másolt képek is nagyíthatók
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
// "Üzenet másolása" gomb a programoknál
// Minden id-vel rendelkező .news-card aljára egy gombot tesz, amely a
// program rövid üzenetét a vágólapra másolja, hogy be lehessen illeszteni
// WhatsAppba, Messengerbe vagy bárhova. Az üzenet a kártyából áll össze:
// név, dátum, időpont, helyszín és a program linkje. A kapcsolattartók
// adatai szándékosan nincsenek benne.
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

// A Google Naptár "esemény létrehozása" hivatkozása, előre kitöltve (a látogatónak
// csak a Mentés gombot kell megnyomnia). Ha a kártyán van időpont (pl. "14:00–20:00"
// vagy "17:45"), időponthoz kötött esemény lesz; ha nincs, egész napos.
// Egy időpontnál (pl. gyülekező) alapból 1 órás eseményt hoz létre.
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
    // egész napos: a befejezés napja nem tartozik bele, ezért a következő nap
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
  if (card.closest('#calendarSource') && isPastCard(card)) return;   // lejárt programhoz nem kell
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
// Személyek bemutatkozó ablaka
// A .person-card.has-bio kártyára kattintva felugró ablakban megjelenik a személy
// képe, neve, szerepe, a "Miért keresd?" lista és a másolható e-mail cím(ek).
// A tartalom a kártyán belüli rejtett .person-bio blokkból jön. Bezárás: × gomb,
// háttérre kattintás vagy Esc. A kártyán lévő linkekre/gombokra kattintás nem nyitja meg.
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
      if (node.nodeType === 1 && node.classList.contains('person-bio-role')) return; // a szerep a fejlécben van
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
// Rólunk / Csapatotthonunk: váltakozó "szöveg + fotók" blokkok (mint a Tábor oldalon)
// A .side-photos blokk fotóit és a szöveg szakaszait (h3 címek) a script összepárosítja: a szöveget
// egyenletes hosszúságú részekre bontja, és mindegyik mellé 2-3 fotót tesz kollázsként
// (.camp-block / .camp-media / .camp-col, ugyanaz a stílus, mint a Tábor oldalon). A blokkok
// váltakozva a bal és a jobb oldalra teszik a képeket; telefonon a képek a szöveg fölött állnak.
// ==========================================================
(function initSplitBlocks() {
  document.querySelectorAll('.has-side-photos').forEach(section => {
    const holder = section.querySelector('.side-photos');
    const text = section.querySelector('.prose, .home-story');
    if (!holder || !text) return;
    const images = [...holder.querySelectorAll('img')];
    if (images.length === 0) return;

    // a szöveg szakaszai: minden h3-tól a következő h3-ig (a forrás-sor a végén marad)
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

    // a szakaszokat összefüggő, hozzávetőleg egyenlő hosszú részekre osztjuk
    const chunks = [];
    let chunk = [];
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
    if (chunk.length) chunks.push(chunk);

    const base = Math.floor(images.length / chunks.length);
    const extra = images.length % chunks.length;
    const fragment = document.createDocumentFragment();
    // a blokkok helye: az első cím elé tett jelölő (maga a cím is átkerül a szövegdobozba)
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
        // 3 kép: egy lépcsőzetes, egymásra kissé ráfedő oszlop (nem két oszlop)
        media.classList.add('camp-media-3');
        blockImages.forEach(img => media.append(img));
      } else {
        // oszlopok: az első oszlopba kevesebb vagy ugyanannyi kép, a másodikba a többi
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
// Pénzügyek oldal: fülek (Tagdíj / Nagytábordíj / Kcs tábordíj) és időablak
// Fülsáv nincs (a tulajdonos kérése): a fül a címben lévő #tagdij / #nagytabor /
// #kcstabor alapján nyílik, azaz a menü Pénzügyek lenyílójából; cím nélkül a Tagdíj.
// Időszak: a fülnek (.fee-panel) a data-from / data-until napjai között látszik a
// tartalma (a vég napja még beleszámít; data-until nélkül nincs vége); azon kívül,
// vagy ha nincs data-from, a .fee-empty alapüzenet. A tartalmat a Google Táblázatból
// a tools/sync_penzugyek.py írja. Teszt a konzolban:
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
}

(function initFeeTabs() {
  const panels = [...document.querySelectorAll('.fee-panel[data-tab]')];
  if (panels.length === 0) return;
  const names = panels.map(panel => panel.dataset.tab);
  const menuLinks = [...document.querySelectorAll('#subFinance a')];

  function select(name) {
    if (!names.includes(name)) name = names[0];
    panels.forEach(panel => {
      panel.hidden = panel.dataset.tab !== name;
      // a beágyazott űrlap (Google) csak akkor töltődik be, ha a fülje látszik
      if (!panel.hidden) panel.querySelectorAll('iframe[data-src]').forEach(frame => {
        frame.src = frame.dataset.src;
        frame.removeAttribute('data-src');
      });
    });
    menuLinks.forEach(link => {
      if (link.hash === `#${name}`) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }

  window.addEventListener('hashchange', () => select(location.hash.slice(1)));
  select(location.hash.slice(1));
  updateFees();
})();
