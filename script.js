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
