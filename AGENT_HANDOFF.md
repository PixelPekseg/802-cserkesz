# 802. sz. Szent Korona Cserkészcsapat – weboldal: átadó dokumentum (AI agentnek / fejlesztőnek)

Cél: egy másik AI agent vagy fejlesztő ebből a fájlból megértse, hogyan működik az oldal, és biztonságosan tudja **frissíteni, bővíteni vagy hibát javítani**.
A részletes, folyamatosan karbantartott felhasználói útmutató a [README.md](README.md); ez a fájl a háttér, a döntések és a buktatók gyűjteménye.
(A szerzői cég másik három oldaláról – pixelpekseg, fodrasz-demo, volkov_oleh – a `../PIXELPEKSEG_AGENT_HANDOFF.md` szól, angolul.)

A tulajdonos magyarul kommunikál; magyarul válaszolj neki. Az oldal **csak magyar nyelvű**, nincs `en/`, `de/`.

---

## 1. Kontextus

- Ügyfél: az **802. sz. Szent Korona Cserkészcsapat** (Gödöllő). Az oldalt a tulajdonos (a csapat tagja, egyben a Pixelpékség webügynökség tulajdonosa) készíti **önkéntesen/csapatprojektként**, nem a szokásos ügyfélmodellben.
- Az oldal célja: toborzás (4–8. osztályos gyerekek és szüleik), a közelgő programok és táborok bemutatása, rajparancsnokok elérhetősége, a Bezsilla csapatotthon bemutatása, támogatás (SZJA 1%, palackvisszaváltás, banki átutalás).
- Szerkesztők: a csapat több tagja **nem programozó**. Ezért a gyakran változó tartalom (programok, táborok, rajok) **Google Táblázatból** kerül az oldalra automatikusan; a többi tartalmat a tulajdonos szerkeszti a kódban.
- Hosting: **GitHub Pages**, repo `PixelPekseg/802-cserkesz`, ág: `main`, gyökér.
  Élő cím: `https://pixelpekseg.github.io/802-cserkesz/`.
  **Saját domain még nincs megvásárolva**; addig mindenhol a `https://www.YOUR-DOMAIN-HERE.com` placeholder áll (minden HTML-ben, `robots.txt`, `sitemap.xml`). Domain után: keresés-csere az egész projektben (`grep -R "YOUR-DOMAIN-HERE" .`), `CNAME` fájl, Pages → Custom domain, Search Console.
- Git: remote `git@github-pixelpekseg:PixelPekseg/802-cserkesz.git` (SSH alias a Pixelpékség kulcsához). Git felhasználó: `kissgergely12`. **Csak a tulajdonos pusholja** – ne commitolj/pusholj, amíg nem kéri.
  `pull.rebase=true` be van állítva, mert a robot (GitHub Actions) is commitol a `main`-re. Push előtt mindig `git pull`.

---

## 2. Architektúra röviden

Statikus, többoldalas HTML + egy `style.css` + egy `script.js`, build lépés nélkül.

```
index.html          Főoldal (cím/hero, Csapatunk, Kapcsolat + kapcsolati kártyák és bemutatkozó ablak, FB/IG gombok)
rolunk.html         Rólunk (Csapatunkról, Cserkészetről)
tabor.html          Tábor (kártyák a Táblázatból + általános infó váltakozó kép/szöveg blokkokkal)
csatlakozom.html    Csatlakozom (4–8. osztály, rajparancsnokok kártyái a Táblázatból)
csapatotthon.html   Csapatotthonunk (Bezsilla villa, térkép, elérhetőség)
programok.html      Programok (léptethető hírdobozok + naptár, Táblázatból)
tamogass.html       Támogass minket (SZJA 1%, palackvisszaváltás QR, egyesület adatai, számlaszám)
dokumentumok.html   Dokumentumok (pdf/ mappa; csak a láblécből linkelt)
404.html            Egyedi hibaoldal
style.css, script.js
robots.txt, sitemap.xml
images/webp/…       használt képek (oldalankénti mappák)
images/originals/…  eredetik (.gitignore-ban, nem kerülnek fel)
pdf/                letölthető dokumentumok
data/*.csv          a Táblázatból utoljára letöltött pillanatképek (+ keepalive.txt)
tools/*.py          a Táblázat → HTML generátorok
.github/workflows/sync-tablazat.yml
drafts/             kész, de nem publikált anyagok (.gitignore-ban): adatkezeles.html, régi xlsx-ek
```

- **A fejléc és a lábléc minden HTML fájlban külön szerepel** (8 oldal + 404). Menü-/lábléc-módosítást mindenhol át kell vezetni; utána `diff`-eld az oldalakat.
- **Jekyll-csapda:** a GitHub Pages figyelmen kívül hagyja az `_`-lal kezdődő mappákat. Ezért `images/webp`, `images/originals`, `drafts` (korábban `_webp` stb. volt, a képek emiatt nem látszottak). **Soha ne nevezz el mappát `_`-lal.** `.nojekyll` nincs és nem kell.
- **Cache-bust:** a HTML-ek `style.css?v=71` és `script.js?v=38` formában hivatkoznak a fájlokra (az utolsó ismert állapot). Bármely CSS/JS módosítás után **minden HTML-ben emeld a számot** (`sed`-del vagy ciklussal), különben a böngésző/CDN a régit mutatja.

---

## 3. Dizájn

- Színek (`style.css` `:root`): `--color-primary #386641` (sötétzöld), `--color-primary-dark #2a4d31`, `--color-accent #6a994e`, `--color-highlight #a7c957`, szöveg `#233f2a`, háttér `#f4f9eb`, váltó háttér `#e8f1d2`, szegély `#d3e4ab`. A három megadott zöld az alap, a világos színek ebből levezetettek. Elég a változókat átírni.
- Betűk: címsorokhoz Georgia, törzshez Segoe UI/Arial. Mobil-first.
- Képkezelési elvek (a tulajdonos kifejezett kérései):
  - a kép mindig **teljes egészében látszódjon** (ne vágd, ne torzítsd),
  - **ne legyen keret**, lekerekített sarkok igen,
  - a Rólunk/Csapatotthon/Tábor oldalon a képek **kollázsként**, enyhén egymásba csúszva, váltakozó oldalon kerülnek a szöveg mellé; a három kép egymás mellé tett kétoszlopos elrendezése "nem jó" volt, helyette lépcsőzetes egyoszlopos kollázs van.

---

## 4. A Táblázat → oldal automatizmus (a legfontosabb rész)

### 4.1 Működés
1. A csapat közös **Google Táblázatának** három adatlapja van: **Programok**, **Táborok**, **Rajok** (mindegyikhez van külön útmutató-lap, amely az oszlopokat írja le). Mindegyik lap külön, **CSV-ként közzé van téve** („Közzététel a weben”).
2. A `.github/workflows/sync-tablazat.yml` **óránként** (cron `23 * * * *`) és kézzel is (Actions → „Oldal frissítése a táblázatból” → Run workflow) lefuttatja a három szkriptet:
   - `tools/sync_programok.py` → `programok.html` (`<!-- PROGRAMOK:START … -->` … `<!-- PROGRAMOK:END -->`)
   - `tools/sync_taborok.py` → `tabor.html` (`TABOROK:START/END`)
   - `tools/sync_rajok.py` → `csatlakozom.html` (`RAJOK:START/END`)
   - közös segédfüggvények: `tools/sync_common.py` (`sync_programok.py` önálló, de ugyanazokat az elveket követi). Csak a Python standard könyvtárát használják.
3. A CSV-címek a workflow fájlban vannak (`PROGRAMOK_CSV_URL`, `TABOROK_CSV_URL`, `RAJOK_CSV_URL`). **Új táblázatnál/lapnál itt kell átírni.**
4. A munkafolyamat a változásokat (`programok.html tabor.html csatlakozom.html data/`) `github-actions[bot]` néven commitolja és pusholja „Oldal frissítése a táblázatból” üzenettel, majd a Pages újraépít.
5. Havonta egy apró „életjel” (`data/keepalive.txt`, `date +%Y-%m`) készül, mert a GitHub 60 nap tevékenység nélkül leállítja az ütemezett workflow-t.

### 4.2 Késleltetések (amiket a felhasználónak el kell mondani)
Táblázat mentése → Google CSV-gyorsítótár ~5 perc → a következő óránkénti futás (vagy kézi indítás) → Pages build ~1–3 perc → böngésző/CDN gyorsítótár akár 10 perc. Tehát egy módosítás akár ~egy óra alatt jelenik meg; sürgős esetben kézzel kell indítani a workflow-t. A Google Táblázat automatikusan ment, külön mentés nem kell.

### 4.3 Hibakezelés
- Hibás egyedi sort a szkript kihagy, és figyelmeztetést ír (`::warning::`).
- Ha a CSV nem érhető el, a fejléc elromlott vagy nincs érvényes sor, a szkript **hibával leáll és nem módosít semmit** → az oldal az utolsó jó állapotot mutatja; a futás pirosan jelenik meg az Actions fülön.
- A fejlécet a szkript az oszlopnevek **eleje alapján** (kisbetűsen) keresi, így apró átfogalmazás nem töri el, de az oszlop törlése/átnevezése igen (kötelező: Név, Kezdő dátum, Megjelenjen?).
- A következő workflow-lépések `if: !cancelled()` miatt egy hibás lap esetén is lefutnak.
- A kártyákat a szkript HTML-escape-eli; az e-mail címeket ellenőrzi (érvénytelent kihagy).
- Helyi kipróbálás: `python3 tools/sync_taborok.py --file valami.csv` (ugyanígy `--url`), a repo tartalmát módosítja, ezért utána `git diff`.

### 4.4 Programok lap
Oszlopok: Név · Kezdő dátum · Befejező dátum (ha több napos) · Kezdő idő · Befejező idő · Időpont megjegyzése (pl. gyülekező) · Helyszín · Leírás · Kapcsolattartó 1 neve · Kapcsolattartó 1 e-mail **vagy telefon** · Kapcsolattartó 2 neve · Kapcsolattartó 2 e-mail vagy telefon · Facebook-esemény linkje · Megjelenjen? (`igen`/üres).
- Kártya sémája: dátum-címke, cím, leírás (a Facebook-esemény linkje a leírás végén „Részletek a Facebook-eseményen” hivatkozásként), `Helyszín`, `Időpont`, „Kérdés esetén keresd:” blokk. Ha nincs kapcsolattartó, a `script.js` a `#newsGrid` `data-default-contact-name/-email` értékét írja be (jelenleg a programokért felelős csapatparancsnok-helyettes).
- A kártyák `id`-je név+dátum alapú slug (pl. `cserkeszmise-20261011`), `data-date` ISO dátummal.
- Dátumformátum a Táblázatban: `2026.10.11.`.
- **Lejárat (a `script.js` `updateNews()`):** az esemény napja után a kártya „Elmúlt” címkével, halványítva a lista végére kerül, majd `data-keep-days` (alapból 7) nap után elrejtődik; a naptárban megmarad. Üres lista esetén üzenet + Facebook/Instagram linkek. Teszt a konzolban: `updateNews(new Date('2026-10-12T10:00:00'))`. A HTML-ből a régi blokkokat a következő szinkron úgyis kicseréli.
- Időpont nélküli program egész napos eseményként kerül a Google Naptárba.
- A kártyákon „Hozzáadás Google Naptárhoz” gomb és megosztási ablak van (a script `buildCalendarLink`, `buildShareMessage`). A WhatsApp/Messenger közvetlen megosztás **szándékosan ki lett véve** (az Apple/WhatsApp asztali megosztás csak a linket küldi el); marad az „Üzenet másolása” gomb.
- A naptár fix magasságú, a hírdobozok sorban léptethetők, kerek nyilakkal mindkét oldalon; letiltott nyíl elhalványul.
- A „Közelgő programok” felugró fül telefonon még részben **rálóg a hero-ra** (ismert, megoldás felajánlva, nincs kérve).

### 4.5 Táborok lap
Oszlopok: Név · Rövid leírás · Időpont (szabad szöveg) · Helyszín · Főszervező 1–3 (név, e-mail, telefon) · Megjelenjen?
Jelenleg két tábor: **Kiscserkésztábor** (5 nap, most 4. osztályt végzőknek) és **Nagytábor** (az 5. osztályt végzők 6 napra jönnek, mindenki más 10 napra). Időpont/helyszín: „Hamarosan frissítjük!” amíg nincs megadva. Az e-mailek és telefonszámok opcionálisak, bármelyik kombináció kezelt.

### 4.6 Rajok lap
Oszlopok: Raj neve · Indulás éve (a tanév kezdő éve, amikor a raj 4. osztályos volt) · Jelenlegi osztály (automatikus, ne írd át) · Rajparancsnok 1–3 (név, e-mail, telefon) · Megjelenjen?
- A **„Jelenlegi osztály” oszlop a Táblázatban képlet**, de az oldal nem erre támaszkodik: a `script.js` `updateGrades()` minden megnyitáskor kiszámolja az osztályt az „Indulás éve” alapján, így a **szeptember 1-jei léptetés magától megtörténik** (a kártyák `data-grade` és `data-school-year` attribútumot hordoznak). A 9. osztályba lépett raj eltűnik (4–8. látszik); ha egy osztályhoz nincs raj, „Hamarosan frissítjük!” felirat áll.
- Új 4. osztályos raj: új sor a Táblázatban, jövőbeli indulási évvel előre is felvehető (addig rejtve marad).

### 4.7 Ha a Táblázat átszervezése kell
Új lap hozzáadása = új CSV-közzététel + új `*_CSV_URL` a workflow-ban + új szkript a `sync_common.py` mintájára + új marker-pár a célfájlban + a `git add` sor kiegészítése a workflow-ban.

---

## 5. Oldalankénti tudnivalók

- **Főoldal:** hero és „Csapatunk” kép+szöveg (asztalon a 802-es légifotó bal oldalon, telefonon nyitókép; csoportkép a Csapatunk szekcióban), Kapcsolat: kártyák 2 oszlopban telefonon. A kártyákra kattintva **bemutatkozó ablak** nyílik (kép, név, szerep, „Miért keresd?” lista, másolható e-mail). A szöveg a kártyán belüli rejtett `<div class="person-bio">`-ban van; **telefonszámok szándékosan nincsenek** az ablakban. Fotó nélkül monogram látszik (`images/webp/kozos/team/`).
- **Facebook / Instagram:** csak **linkgombok** (802szentkorona; csapatotthon: gdlcserkeszhaz / bezsilla.villa), a tartalom nincs betöltve – így kattintás előtt nincs külső süti/adatátadás. Ne tegyél vissza beágyazott widgetet adatkezelési átgondolás nélkül.
- **Rólunk / Csapatotthonunk:** a fotók az oldal végén a `.side-photos` blokkban vannak; a `script.js` (`initSplitBlocks()`) a szöveget a h3 címek mentén egyenlő részekre bontja, és mindegyik mellé 2–3 fotót tesz váltakozó oldalra (telefonon a szöveg fölé). JS nélkül a fotók rácsban a szöveg alatt látszanak. Új kép = a `.side-photos` blokkba. A script egy placeholder megjegyzés-csomópontot (`marker`) használ a darabolásnál – ne cseréld vissza a referencia-csomópont beszúrására (volt `HierarchyRequestError`).
- **Tábor:** fent kártyák (Táblázat), alatta általános információ váltakozó kép+szöveg blokkokkal; a képek `images/webp/tabor/` (nagy) és `tabor/thumb/` (az oldalon látszó bélyeg; kattintásra a nagy nyílik). Letölthető PDF-ek a `pdf/` mappában (felszerelési lista, EU-nyilatkozat, belépési nyilatkozatok).
- **Csatlakozom:** 4.–8. osztályosok, rajparancsnokok kártyái (Táblázat).
- **Csapatotthonunk:** Bezsilla villa, hat fotó (`bezsilla1–6.webp`, kattintásra nagyítható), Google Maps beágyazás, elérhetőség, FB/IG gombok, Grébel Hanna kártya bemutatkozó ablakkal.
- **Támogass minket:** szöveg, SZJA 1% kép (`ado1.webp`), két kártya (egyesület adatai, banki átutalás; adószám/számlaszám **másolás gombbal**), palackvisszaváltás QR-kód (`palack_qrkod.jpg` **szándékosan JPG**, hogy beolvasható maradjon). A szövegben a visszaváltási díj „közvetlenül az egyesület számlájára érkezik” (a tulajdonos kérésére nem szerepel, hogy ki kapja vagy nem kapja).
- **Másolás gombok:** kis, ikon-stílusú gombok minden e-mail mellett (kivéve a láblécben és az eseménykártyákon).
- **Dokumentumok:** a `pdf/` fájljai; csak a láblécből érhető el.
- **404.html:** egyedi hibaoldal.
- **SEO:** `robots.txt`, `sitemap.xml` (jelenleg `YOUR-DOMAIN-HERE`), `share.jpg` (1200×630) megosztási kép, JSON-LD logó: `logo_white.jpg`.

---

## 6. Képek

- Új kép: eredeti → `images/originals/<oldal>/`, WebP (kb. 1000–1600 px széles, minőség ~80) → `images/webp/<oldal>/`, és abból hivatkozz. Hero ~1600 px, személyfotó ~400 px elég.
- Kivétel: QR-kód JPG, megosztási kép JPG.
- A kép betöltési hibáját a `script.js` kezeli (hiányzó kép nem töri el az elrendezést).
- **Még nincs megépítve:** Google Drive → repó képszinkron (a tulajdonos kifejezett ötlete: fix képhelyek, a fájlnév csak a sorszámot adja meg). Terv: *nyilvános* Drive-mappa + Google API-kulcs (nem szolgáltatási fiók), GitHub Secrets: `GOOGLE_API_KEY`, `DRIVE_FOLDER_ID`, naponta futó szkript. Hiányzik a mappa azonosítója és a titkok felvétele. **Az API-kulcs egyszer nyilvánosan kikerült a csevegésben – újra kell generálni, mielőtt bármit használnak, és soha nem szabad fájlba/repóba írni.** Egy felesleges Cloud-projekt (`gleaming-motif-511209-b6`) leállítása is hátra van.

---

## 7. Ismert buktatók

1. `_` kezdetű mappa → a Pages nem szolgálja ki (lásd 2. pont).
2. CSS/JS változtatás után elfelejtett `?v=` emelés → a felhasználó a régit látja.
3. A robot-commitok miatt „divergent branches”: `git pull` (rebase) push előtt.
4. A `programok.html`, `tabor.html`, `csatlakozom.html` marker közötti része **minden szinkronnál felülíródik** – kézi szerkesztés elvész. Az oldal többi része szerkeszthető.
5. A Táblázat oszlopait nem szabad törölni/átnevezni a szkript tudta nélkül (4.3).
6. A CSV Google-oldali gyorsítótára és a Pages build miatt a változás nem azonnali.
7. Korábbi CSS-hiba: a `index('.camp-media {')` típusú szövegcsere hosszabb szelektort is eltalált és levágta a CSS-t – szerkesztéskor ellenőrizd, hogy a fájl végig megvan.
8. A WhatsApp-megosztás csak linket visz át; ne építsd vissza.
9. Beágyazott harmadik féltől származó tartalom (Facebook/Instagram widget) szándékosan nincs.
10. A lenti „Még placeholder” lista a README-ben is szerepel; ne publikáld élesen a `@example.com` és `YOUR-DOMAIN-HERE` értékekkel.

---

## 8. Nyitott feladatok (állapot: 2026-10-11)

- **Domain megvásárlása**, majd a `YOUR-DOMAIN-HERE` placeholderek lecserélése, `CNAME`, Search Console, sitemap beküldése. (Az ügyfél-modell szerint a domain a szervezet nevén lenne – ez itt a tulajdonossal egyeztetendő.)
- **Tábor adatok** (időpont, helyszín, főszervezők) – a Táblázatban kell kitölteni; a README szerinti `@example.com` helyőrzők ellenőrzendők.
- **Adatkezelési tájékoztató:** megírva a `drafts/adatkezeles.html`-ben (nem publikálva, a kép-kezelést a tulajdonos már papíron lerendezte; a Google Maps és a GitHub hosting miatt szerepel). Publikáláskor linkelni kell a láblécből.
- **Drive-képszinkron** (6. pont), kulcs-újragenerálás, felesleges Cloud-projekt leállítása.
- Lehetséges bővítések, amiket felajánlottunk: a Programok lapon külön e-mail/telefon oszlop; „Szövegek” és „Beállítások” lap a Táblázatban (szöveges blokkok soronként egy bekezdéssel, linkek/térkép a Táblázatból); a felugró „Közelgő programok” fül telefonos átfedésének javítása; a workflow-ban használt action-verziók frissítése (`actions/checkout@v4`, `setup-python@v5`).
- **Függő helyi módosítások:** a legutóbbi munkamenet végén vannak commitolatlan változások; ellenőrizd `git status`-szal, és a tulajdonos döntse el, mikor commitol/pusholja.

---

## 9. Munkamódszer-ajánlás új agentnek

1. Olvasd el a `README.md`-t és ezt a fájlt, majd `git status` / `git log --oneline | head`.
2. Módosítás előtt helyi szerverrel (`python3 -m http.server`) nézd meg asztali és telefonos szélességben (≈375 px).
3. Táblázat-eredetű szakaszhoz ne nyúlj kézzel; a szkriptet vagy a Táblázatot módosítsd.
4. Minden CSS/JS változás után emeld a `?v=` számot az összes HTML-ben.
5. Kis, célzott módosításokat végezz; a tulajdonos gyakran finomít (képek elrendezése, szövegek), és kifejezett, konkrét vizuális elvárásai vannak (3. pont).
6. Soha ne kérj/írj be kulcsot, jelszót a repóba; a titkok a GitHub Secrets-ben vannak.
7. Commitot/pusht csak kérésre.
