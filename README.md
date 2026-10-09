# 802. sz. Szent Korona Cserkészcsapat – weboldal

Statikus (HTML/CSS/JS) többoldalas weboldal, backend nélkül, GitHub Pages-en közvetlenül publikálható. Csak magyar nyelvű.

## Fájlstruktúra

- `index.html` – Főoldal (borítókép + név, Csapatunk (kép + szöveg), Kapcsolat, Facebook- és Instagram-gombok)
- `rolunk.html` – Rólunk (két pont: Csapatunkról, Cserkészetről; a szöveg a csapat korábbi honlapjáról, a 802szentkorona.hu-ról származik)
- `tabor.html` – Tábor (kiscserkésztábor és nagytábor kártyák, általános információk váltakozó kép + szöveg blokkokkal; a képek az `images/camp/`, a letölthető PDF-ek a `pdf/` mappában)
- `csatlakozom.html` – Csatlakozom (4.–8. osztály, rajparancsnokok)
- `csapatotthon.html` – Csapatotthonunk (Bezsilla villa, elérhetőség, Google Maps, Facebook- és Instagram-gombok)
- `programok.html` – Programok (hírdobozok léptethető sorban + naptár)
- `tamogass.html` – Támogass minket (adó 1%-os kép, egyesület adatai, számlaszám)
- `style.css`, `script.js` – közös kinézet és működés (mobil menü, hiányzó képek kezelése)
- `robots.txt`, `sitemap.xml` – Google-kereshetőséghez

A fejléc és a lábléc mind a 7 HTML fájlban külön szerepel – ha módosítod a menüt vagy a láblécet, **mind a 7 fájlban** át kell vezetni.

## Képek (töltsd fel ezekkel a nevekkel)

- `images/hero.webp` – a "Csapatunk" szekció bal oldali képe (a 802-es szám); teljes egészében látszik, levágás nélkül
- `images/csapatunk.webp` – a főoldal borítóképe (csoportkép) a név mögött; bármilyen arányú lehet, teljes szélességben, levágás nélkül látszik (a magassága az arányából adódik, nagy képernyőn a képernyőnél magasabb is lehet); amíg nincs, zöld színátmenet látszik
- `images/logo_white.jpg` (fekete jel fehér alapon) – a fejlécben látszik, a fehér háttér átlátszóvá válik; `images/logo_green.jpg` – favicon; `images/logo_black.jpg` – jelenleg nincs használatban
- `images/bezsilla.webp`, `images/bezsilla_bipi.webp` – a Csapatotthonunk oldal két képe (a villa, illetve a falra festett Baden-Powell-portré); egymás mellett, azonos magassággal, levágás nélkül látszanak, mobilon egymás alatt
- `images/palack_qrkod.jpg` – a palackvisszaváltáshoz beolvasandó QR-kód (egyedi azonosító) a Támogass minket oldal alján
- `images/ado1.webp` – az adó 1%-os kép a Támogass minket oldalon, a bevezető szöveg alatt
- `images/team/cseri-holzman_lili.webp`, `csiki_adam.webp`, `grebel_hanna.webp`, `bedo_gergely.webp`, `peter_anna.webp` – a kapcsolati kártyák fotói (amíg nincs, monogram látszik)

Képformátum: az oldal WebP képeket használ (kisebbek, gyorsabbak). A tábor képekből kettő van: `images/camp/thumb/` (kicsi, ez látszik az oldalon) és `images/camp/` (nagy, ez nyílik meg kattintásra). A régi JPG-k az `images/_jpg-originals/` és `images/camp/originals/` mappákban vannak (a .gitignore kizárja). Új képet is WebP-re alakíts, mielőtt feltöltöd (a borítókép ~1600 px széles, a személyek fotói ~400 px elég), különben lassul az oldal.

## Színek

A `style.css` elején lévő `:root` blokkban vannak (386641, 6a994e, a7c957 az alap, a háttér- és szegélyszínek ezekből levezetettek). Elég ezeket átírni.

## Karbantartás

- **Új hír / esemény:** az `programok.html`-ben másolj le egy `<article class="news-card">…</article>` blokkot, írd át a szöveget, a látható dátumot (`.news-date`), és állítsd be a `data-date="ÉÉÉÉ-HH-NN"` attribútumot az esemény napjára (többnapos eseménynél add meg a `data-end-date`-et is).
- **Megosztás gomb:** minden programkártyán (az `id`-val rendelkezőn) automatikusan megjelenik. Telefonon a készülék megosztó ablakát nyitja, számítógépen WhatsApp / Messenger / üzenetmásolás menü (a Messengernél az üzenet a vágólapra kerül, és megnyílik a Messenger)t. Az üzenet a kártyából áll össze (név, dátum, időpont, helyszín, link, emojikkal), a kapcsolattartók nincsenek benne. Működéséhez az `id` kell a kártyán, és élesben a végleges domain.
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
