# 802. sz. Szent Korona Cserkészcsapat – weboldal

Statikus (HTML/CSS/JS) többoldalas weboldal, backend nélkül, GitHub Pages-en közvetlenül publikálható. Csak magyar nyelvű.

## Fájlstruktúra

- `index.html` – Főoldal (borítókép + név, Csapatunk (kép + szöveg), Kapcsolat, Facebook- és Instagram-widget)
- `rolunk.html` – Rólunk (két pont: Csapatunkról, Cserkészetről; a szöveg a csapat korábbi honlapjáról, a 802szentkorona.hu-ról származik)
- `csatlakozom.html` – Csatlakozom! (4.–12. osztály, rajparancsnokok)
- `csapatotthon.html` – Csapatotthonunk (Bezsilla villa, elérhetőség, Google Maps, Facebook- és Instagram-widget)
- `aktualis.html` – Aktuális (hírdobozok)
- `tamogass.html` – Támogass minket (adó 1%-os kép, egyesület adatai, számlaszám)
- `style.css`, `script.js` – közös kinézet és működés (mobil menü, hiányzó képek kezelése)
- `robots.txt`, `sitemap.xml` – Google-kereshetőséghez

A fejléc és a lábléc mind a 6 HTML fájlban külön szerepel – ha módosítod a menüt vagy a láblécet, **mind a 6 fájlban** át kell vezetni.

## Képek (töltsd fel ezekkel a nevekkel)

- `images/hero.jpg` – a "Csapatunk" szekció bal oldali képe (a 802-es szám); teljes egészében látszik, levágás nélkül
- `images/csapatunk.jpg` – a főoldal borítóképe (csoportkép) a név mögött; bármilyen arányú lehet, teljes szélességben, levágás nélkül látszik (a magassága az arányából adódik, nagy képernyőn a képernyőnél magasabb is lehet); amíg nincs, zöld színátmenet látszik
- `images/logo_white.jpg` (fekete jel fehér alapon) – a fejlécben látszik, a fehér háttér átlátszóvá válik; `images/logo_green.jpeg` – favicon; `images/logo_black.jpeg` – jelenleg nincs használatban
- `images/ado1.jpg` – az adó 1%-os kép a Támogass minket oldalon, a bevezető szöveg alatt (az `ado1.png` tömörítetlen eredeti, nem kerül a repóba – a `.gitignore` kizárja)
- `images/team/cseri-holzman_lili.jpg`, `csiki_adam.jpg`, `grebel_hanna.jpg`, `bedo_gergely.jpg`, `peter_anna.jpg` – a kapcsolati kártyák fotói (amíg nincs, monogram látszik)

Tömörítsd a képeket feltöltés előtt (a hero ~1920px széles, a személyek fotói ~400×400 px elég), különben lassul az oldal.

## Színek

A `style.css` elején lévő `:root` blokkban vannak (386641, 6a994e, a7c957 az alap, a háttér- és szegélyszínek ezekből levezetettek). Elég ezeket átírni.

## Karbantartás

- **Új hír / esemény:** az `aktualis.html`-ben másolj le egy `<article class="news-card">…</article>` blokkot, írd át a szöveget, a látható dátumot (`.news-date`), és állítsd be a `data-date="ÉÉÉÉ-HH-NN"` attribútumot az esemény napjára (többnapos eseménynél add meg a `data-end-date`-et is).
- **Lejárt események (automatikus):** az esemény napja után az esemény `Elmúlt` címkével, halványítva a lista végére kerül, majd a rács (`#newsGrid`) `data-keep-days` attribútumában megadott nap (alapból 7) után elrejtődik. Ha nincs látható hír, egy üzenet jelenik meg a Facebook/Instagram linkekkel. A `data-date` nélküli hír mindig látszik. Elrejtés csak a böngészőben történik, a HTML-ből néha érdemes kitörölni a régi blokkokat. Teszteléshez a böngésző konzoljában: `updateNews(new Date('2026-10-12T10:00:00'))`.
- **Támogass minket oldal:** fent a szöveg, alatta az adó 1%-os kép (`ado1.jpg`), majd két kártya egymás mellett (egyesület adatai, banki átutalás); mobilon egymás alá kerülnek.
- **Rajparancsnokok:** a `csatlakozom.html`-ben osztályonként (4–8.) szerepel a raj neve, a rajparancsnokok neve és saját e-mail címe.
- **Facebook- és Instagram-widget:** a főoldalon (802szentkorona) és a csapatotthon oldalon (gdlcserkeszhaz / bezsilla.villa) azonnal betöltődnek, és a legutóbbi bejegyzéseket mutatják. Fontos: a beágyazott tartalom miatt a Facebook és az Instagram sütiket állíthat be a látogatónak. Másik oldal/profil beállításához az iframe `src`-ben cseréld le az oldal nevét, és a "Megnyitás" linkeket is.

## Még placeholder (cserélendő)

- Csapatotthon szövege (`csapatotthon.html`)
- `https://www.YOUR-DOMAIN-HERE.com` az összes HTML fájlban, a `robots.txt`-ben és a `sitemap.xml`-ben

## Publikálás GitHub Pages-re

1. Repó létrehozása, a mappa tartalmának feltöltése (git init, add, commit, push).
2. Repo **Settings → Pages**: `main` ág, gyökér mappa.
3. Saját domain esetén: **Settings → Pages → Custom domain**, és a DNS beállítása.
