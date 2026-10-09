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
// Aktuális év a láblécben
// ==========================================================
document.getElementById('year').textContent = new Date().getFullYear();

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
// Minden .news-card a data-date (és opcionálisan data-end-date)
// attribútuma alapján "közelgő" vagy "lejárt". A lejárt események az
// esemény napja után a rács data-keep-days attribútumában megadott
// ideig (alapból 7 nap) "Elmúlt" címkével, halványítva a lista végén
// látszanak, utána elrejtődnek. Ha minden elrejtődik, egy üres-állapot
// üzenet jelenik meg. A data-date nélküli hír mindig látszik.
// Az updateNews(now) tetszőleges időponttal újrafuttatható (tesztelés).
// ==========================================================
function updateNews(now = new Date()) {
  const grid = document.getElementById('newsGrid');
  const emptyMessage = document.getElementById('newsEmpty');
  if (!grid) return;

  const keepDays = Number.parseFloat(grid.dataset.keepDays);
  const keepMs = (Number.isFinite(keepDays) ? keepDays : 7) * 24 * 60 * 60 * 1000;

  // Az eredeti (HTML-beli) sorrendet megjegyezzük, hogy többször is lefuttatható legyen
  const cards = [...grid.querySelectorAll('.news-card')];
  cards.forEach((card, index) => {
    if (!card.dataset.order) card.dataset.order = String(index);
  });
  cards.sort((a, b) => Number(a.dataset.order) - Number(b.dataset.order));

  const upcoming = [];
  const past = [];

  cards.forEach(card => {
    card.hidden = false;
    card.classList.remove('news-card-past');
    card.querySelectorAll('.news-past-label').forEach(label => label.remove());

    const endDate = card.dataset.endDate || card.dataset.date;
    const eventEnd = endDate ? new Date(`${endDate}T23:59:59`) : null;

    if (!eventEnd || Number.isNaN(eventEnd.getTime()) || now <= eventEnd) {
      upcoming.push(card);
    } else if (now - eventEnd > keepMs) {
      card.hidden = true;
    } else {
      card.classList.add('news-card-past');
      const label = document.createElement('span');
      label.className = 'news-past-label';
      label.textContent = 'Elmúlt';
      card.querySelector('.news-meta').append(label);
      past.push(card);
    }
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
      const newsLink = card.querySelector('.news-link');
      if (newsLink) newsLink.before(contact);
      else card.append(contact);
    });
  }

  // Elöl a közelgők, a végén az elmúltak; mindkét csoport dátum szerint
  // növekvő sorrendben (a dátum nélküli hír a közelgők végére kerül)
  const byDate = (a, b) =>
    (a.dataset.date || '9999-12-31').localeCompare(b.dataset.date || '9999-12-31') ||
    Number(a.dataset.order) - Number(b.dataset.order);
  upcoming.sort(byDate);
  past.sort(byDate);
  [...upcoming, ...past].forEach(card => grid.append(card));

  if (emptyMessage) {
    emptyMessage.hidden = grid.querySelector('.news-card:not([hidden])') !== null;
  }

  document.dispatchEvent(new Event('newsupdated'));
}

updateNews();

// ==========================================================
// Főoldal – a következő 7 nap programjainak füle
// A programokat az programok.html hírdobozaiból olvassa ki (data-date /
// data-end-date), így nincs külön adatot karbantartani. Ha nincs közelgő
// program, vagy az programok.html nem olvasható (pl. fájlból megnyitva),
// a fül nem jelenik meg. A bezárást a munkamenet erejéig megjegyzi.
// ==========================================================
async function initUpcomingTab(now = new Date()) {
  const tab = document.getElementById('upcomingTab');
  const list = document.getElementById('upcomingList');
  const closeButton = document.getElementById('upcomingClose');
  if (!tab || !list || !closeButton) return;

  try {
    if (sessionStorage.getItem('upcomingTabClosed') === '1') return;
  } catch (e) { /* a tárolás nem elérhető – a fül megjelenhet */ }

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
    try { sessionStorage.setItem('upcomingTabClosed', '1'); } catch (e) { /* nem baj */ }
  });

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
// Programok – a kártyasor léptetése nyilakkal
// Egyszerre 3 kártya látszik (keskenyebb képernyőn 2, illetve 1); a nyilak
// egy kártyányit lépnek. Ha minden kártya elfér, a nyilak elrejtődnek,
// az első/utolsó helyen a megfelelő nyíl inaktív.
// ==========================================================
function initNewsCarousel() {
  const carousel = document.getElementById('newsCarousel');
  const track = document.getElementById('newsGrid');
  const prev = document.getElementById('newsPrev');
  const next = document.getElementById('newsNext');
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

initNewsCarousel();

// ==========================================================
// Programok – naptár
// A lap kártyáiból (data-date, opcionálisan data-end-date) építi fel a
// havi naptárat. A lejárt, a listából már elrejtett programok is benne
// maradnak. A jelölt napra kattintva a nap programjai jelennek meg alatta.
// ==========================================================
function initCalendar() {
  const root = document.getElementById('calendar');
  const detail = document.getElementById('calendarDetail');
  const track = document.getElementById('newsGrid');
  if (!root || !detail || !track) return;

  const monthNames = ['január', 'február', 'március', 'április', 'május', 'június',
    'július', 'augusztus', 'szeptember', 'október', 'november', 'december'];
  const weekdays = ['H', 'K', 'Sze', 'Cs', 'P', 'Szo', 'V'];
  const pad = n => String(n).padStart(2, '0');
  const dayKey = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;

  const events = [...track.querySelectorAll('.news-card[data-date]')]
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
      // a hónap első napja mellett a hónap rövid neve is látszik (pl. "nov. 1")
      cell.append(element('span', 'cal-num',
        day === 1 ? `${monthNames[date.getMonth()].slice(0, 3)}. 1` : String(day)));

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
