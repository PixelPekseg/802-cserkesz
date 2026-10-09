# 802. sz. Szent Korona Cserkészcsapat – weboldal

Statikus (HTML/CSS/JS) többoldalas weboldal, backend nélkül, GitHub Pages-en közvetlenül publikálható. Csak magyar nyelvű.

## Fájlstruktúra

- `index.html` – Főoldal (borítókép + név, Csapatunk (kép + szöveg), Kapcsolat, Facebook- és Instagram-gombok)
- `rolunk.html` – Rólunk (két pont: Csapatunkról, Cserkészetről; a szöveg a csapat korábbi honlapjáról, a 802szentkorona.hu-ról származik)
- `tabor.html` – Tábor (kiscserkésztábor és nagytábor kártyák, általános információk váltakozó kép + szöveg blokkokkal; a képek az `images/_webp/tabor/`, a letölthető PDF-ek a `pdf/` mappában)
- `dokumentumok.html` – Dokumentumok (a `pdf/` mappa letölthető fájljai; a lábléc linkelte, a menüben nincs)
- `csatlakozom.html` – Csatlakozom (4.–8. osztály, rajparancsnokok)
- `csapatotthon.html` – Csapatotthonunk (Bezsilla villa, elérhetőség, Google Maps, Facebook- és Instagram-gombok)
- `programok.html` – Programok (hírdobozok léptethető sorban + naptár)
- `tamogass.html` – Támogass minket (adó 1%-os kép, egyesület adatai, számlaszám)
- `style.css`, `script.js` – közös kinézet és működés (mobil menü, hiányzó képek kezelése)
- `robots.txt`, `sitemap.xml` – Google-kereshetőséghez

A fejléc és a lábléc mind a 7 HTML fájlban külön szerepel – ha módosítod a menüt vagy a láblécet, **mind a 7 fájlban** át kell vezetni.

## Képek

Minden kép az `images/` mappában van, két fő mappára bontva, azon belül oldalak szerint:

- **`images/_webp/`** – az oldalon használt, tömörített képek (WebP; a QR-kód és a megosztási kép JPG):
  - `fooldal/` – `csapatunk.webp` (a főoldali borítókép, csoportkép; levágva a csoport körül), `hero.webp` (a 802-es légifotó; asztalon a Csapatunk szekció bal oldala, telefonon a nyitókép)
  - `rolunk/` – a Rólunk oldal fotói (a szöveg két oldalán)
  - `tabor/` – a Tábor oldal képei (nagy változat) és `tabor/thumb/` (kis bélyegkép, ez látszik az oldalon; a nagy kattintásra nyílik meg)
  - `csapatotthon/` – `bezsilla.webp`, `bezsilla_bipi.webp`
  - `tamogass/` – `ado1.webp` (adó 1%-os kép), `palack_qrkod.jpg` (palackvisszaváltás QR-kód: szándékosan JPG, hogy beolvasható maradjon)
  - `kozos/` – több oldalon használt képek: `logo_white.webp` / `logo_white.jpg` (fejléc, ill. strukturált adat logója), `logo_green.jpg` (favicon), `logo_black.jpg` (nincs használatban), `share.jpg` (megosztási előnézet, 1200×630), `team/` (a kapcsolati kártyák fotói; amíg nincs fotó, monogram látszik), `pictogram/` (piktogramok, jelenleg nincsenek használatban)
- **`images/_originals/`** – az eredeti, tömörítetlen fotók ugyanilyen oldalankénti bontásban. Ezt a `.gitignore` kizárja, nem kerül a GitHubra.

Új kép felvétele: tedd az eredetit az `_originals/<oldal>/` mappába, készíts belőle WebP-t (kb. 1000–1600 px széles, minőség ~80) az `_webp/<oldal>/` mappába, és abból hivatkozz. A borítókép ~1600 px széles, a személyek fotói ~400 px elég, különben lassul az oldal.

## Színek

A `style.css` elején lévő `:root` blokkban vannak (386641, 6a994e, a7c957 az alap, a háttér- és szegélyszínek ezekből levezetettek). Elég ezeket átírni.

## Karbantartás

- **Új hír / esemény:** az `programok.html`-ben másolj le egy `<article class="news-card">…</article>` blokkot, írd át a szöveget, a látható dátumot (`.news-date`), és állítsd be a `data-date="ÉÉÉÉ-HH-NN"` attribútumot az esemény napjára (többnapos eseménynél add meg a `data-end-date`-et is).
- **Google Naptárba gomb:** minden programkártyán (az `id`-val és `data-date`-tel rendelkezőn) megjelenik; megnyitja a Google Naptárat az eseménnyel előre kitöltve (a látogatónak a Mentés gombot kell megnyomnia). Az "Időpont" sorból veszi az időt (pl. `14:00–20:00`); egy időpontnál 1 órás esemény lesz, időpont nélkül egész napos. A kapcsolattartók nincsenek benne.
- **Üzenet másolása gomb:** minden programkártyán (az `id`-val rendelkezőn) automatikusan megjelenik. Kattintásra a program rövid üzenete (név, dátum, időpont, helyszín, link, emojikkal) a vágólapra kerül, onnan beilleszthető WhatsAppba, Messengerbe stb. A kapcsolattartók nincsenek az üzenetben. Működéséhez az `id` kell a kártyán, és élesben a végleges domain.
- **Lejárt események (automatikus):** az esemény napja után az esemény `Elmúlt` címkével, halványítva a lista végére kerül, majd a rács (`#newsGrid`) `data-keep-days` attribútumában megadott nap (alapból 7) után elrejtődik. Ha nincs látható hír, egy üzenet jelenik meg a Facebook/Instagram linkekkel. A `data-date` nélküli hír mindig látszik. Elrejtés csak a böngészőben történik, a HTML-ből néha érdemes kitörölni a régi blokkokat. Teszteléshez a böngésző konzoljában: `updateNews(new Date('2026-10-12T10:00:00'))`.
- **Támogass minket oldal:** fent a szöveg, alatta az adó 1%-os kép (`ado1.jpg`), majd két kártya egymás mellett (egyesület adatai, banki átutalás); mobilon egymás alá kerülnek.
- **Rajparancsnokok (automatikus léptetés):** a `csatlakozom.html`-ben minden raj kártyáján `data-grade` (osztály) és `data-school-year` (a tanév kezdő éve) van; minden szeptember 1-jén a rajok eggyel feljebb lépnek, a 9. osztályba lépett raj eltűnik (a 4–8. osztály látszik). Új 4. osztályos rajhoz másolj le egy kártyát, írd át a nevet/rajparancsnokokat, és állítsd be `data-grade="4"` + az új tanév kezdő évét (előre is felvehető, addig rejtve marad). Ha az új raj még nincs felvéve, a 4. osztálynál a "Hamarosan frissítjük!" felirat látszik.
- **Facebook / Instagram:** a főoldalon (802szentkorona) és a csapatotthon oldalon (gdlcserkeszhaz / bezsilla.villa) csak linkgombok vannak, a tartalmukat az oldal nem tölti be (így nincs külső süti/adatátadás kattintás előtt). Másik oldalhoz/profilhoz cseréld le a gombok `href`-jét.

## Még placeholder (cserélendő)

- Tábor oldal (`tabor.html`): a két tábor időpontja, helyszíne és a főszervezők neve/e-mail címe (jelenleg "Hamarosan frissítjük!" és `@example.com`)

- Csapatotthon szövege (`csapatotthon.html`)
- `https://www.YOUR-DOMAIN-HERE.com` az összes HTML fájlban, a `robots.txt`-ben és a `sitemap.xml`-ben

## Publikálás GitHub Pages-re

1. Repó létrehozása, a mappa tartalmának feltöltése (git init, add, commit, push).
2. Repo **Settings → Pages**: `main` ág, gyökér mappa.
3. Saját domain esetén: **Settings → Pages → Custom domain**, és a DNS beállítása.
