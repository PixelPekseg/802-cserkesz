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
// Aktuális – a lejárt események automatikus kezelése
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

  // Elöl a közelgők, a végén az elmúltak
  [...upcoming, ...past].forEach(card => grid.append(card));

  if (emptyMessage) {
    emptyMessage.hidden = grid.querySelector('.news-card:not([hidden])') !== null;
  }
}

updateNews();

// ==========================================================
// Főoldal – a következő 7 nap programjainak füle
// A programokat az aktualis.html hírdobozaiból olvassa ki (data-date /
// data-end-date), így nincs külön adatot karbantartani. Ha nincs közelgő
// program, vagy az aktualis.html nem olvasható (pl. fájlból megnyitva),
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
    const response = await fetch('aktualis.html');
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
    link.href = event.id ? `aktualis.html#${event.id}` : 'aktualis.html';
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
