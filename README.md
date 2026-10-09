# 802. sz. Szent Korona Cserkészcsapat – weboldal

Statikus (HTML/CSS/JS) többoldalas weboldal, backend nélkül, GitHub Pages-en közvetlenül publikálható. Csak magyar nyelvű.

## Fájlstruktúra

- `index.html` – Főoldal (borítókép + név, Csapatunk, Kapcsolat, Facebook- és Instagram-widget)
- `csatlakozom.html` – Csatlakozom! (4.–12. osztály, rajparancsnokok)
- `csapatotthon.html` – Csapatotthonunk (Bezsilla villa, elérhetőség, Google Maps, Facebook- és Instagram-widget)
- `aktualis.html` – Aktuális (hírdobozok)
- `tamogass.html` – Támogass minket (számlaszám)
- `style.css`, `script.js` – közös kinézet és működés (mobil menü, hiányzó képek kezelése)
- `robots.txt`, `sitemap.xml` – Google-kereshetőséghez

A fejléc és a lábléc mind az 5 HTML fájlban külön szerepel – ha módosítod a menüt vagy a láblécet, **mind az 5 fájlban** át kell vezetni.

## Képek (töltsd fel ezekkel a nevekkel)

- `images/hero.jpg` – borítókép a főoldalon; bármilyen arányú lehet, teljes egészében látszik (levágás nélkül), a kép melletti sávokat a kép elmosott változata tölti ki (amíg nincs, zöld színátmenet látszik)
- `images/csapatunk.jpg` – a "Csapatunk" szekció háttérképe (amíg nincs, zöld színátmenet)
- `images/logo_white.jpg` (fekete jel fehér alapon) – a fejlécben látszik, a fehér háttér átlátszóvá válik; `images/logo_green.jpeg` – favicon; `images/logo_black.jpeg` – jelenleg nincs használatban
- `images/team/cseri-holzman_lili.jpg`, `csiki_adam.jpg`, `grebel_hanna.jpg`, `bedo_gergely.jpg`, `peter_anna.jpg` – a kapcsolati kártyák fotói (amíg nincs, monogram látszik)

Tömörítsd a képeket feltöltés előtt (a hero ~1920px széles, a személyek fotói ~400×400 px elég), különben lassul az oldal.

## Színek

A `style.css` elején lévő `:root` blokkban vannak (386641, 6a994e, a7c957 az alap, a háttér- és szegélyszínek ezekből levezetettek). Elég ezeket átírni.

## Karbantartás

- **Új hír:** az `aktualis.html`-ben másolj le egy `<article class="news-card">…</article>` blokkot, írd át a dátumot és a szöveget.
- **Rajparancsnokok:** a `csatlakozom.html`-ben osztályonként vannak, a nevek és e-mail címek jelenleg PLACEHOLDEREK (`@example.com`).
- **Facebook- és Instagram-widget:** a főoldalon (802szentkorona) és a csapatotthon oldalon (gdlcserkeszhaz / bezsilla.villa) azonnal betöltődnek, és a legutóbbi bejegyzéseket mutatják. Fontos: a beágyazott tartalom miatt a Facebook és az Instagram sütiket állíthat be a látogatónak. Másik oldal/profil beállításához az iframe `src`-ben cseréld le az oldal nevét, és a "Megnyitás" linkeket is.

## Még placeholder (cserélendő)

- Csapatunk szövege (`index.html`)
- Csapatotthon szövege (`csapatotthon.html`)
- Támogatás szövege, számlaszám és számlatulajdonos (`tamogass.html`)
- Rajparancsnokok nevei és e-mail címei (`csatlakozom.html`)
- `https://www.YOUR-DOMAIN-HERE.com` az összes HTML fájlban, a `robots.txt`-ben és a `sitemap.xml`-ben

## Publikálás GitHub Pages-re

1. Repó létrehozása, a mappa tartalmának feltöltése (git init, add, commit, push).
2. Repo **Settings → Pages**: `main` ág, gyökér mappa.
3. Saját domain esetén: **Settings → Pages → Custom domain**, és a DNS beállítása.
