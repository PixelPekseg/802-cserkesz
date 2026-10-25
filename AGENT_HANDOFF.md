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
programok.html      Programok (közelgő programok + Program Archívum, léptethető kártyák, Táblázatból)
naptar.html         Naptár (naptárnézet; ugyanazok a kártyák rejtve, #calendarSource, Táblázatból)
tamogass.html       Támogass minket (SZJA 1%, palackvisszaváltás QR, egyesület adatai, számlaszám)
penzugyek.html      Pénzügyek (Tagdíj / Nagytábordíj / Kcs tábordíj fülek időablakkal; egyelőre kézi példa, lásd 5. pont)
eszkozok.html       Eszközbérlés (eszközlista + kapcsolattartó a Táblázatból, bevezető szöveg kézzel)
dokumentumok.html   Dokumentumok (pdf/ mappa; csak a láblécből linkelt)
galeria.html        Galéria (az oldal összes fotója/videója; a láblécből linkelt; tools/sync_gallery.py)
404.html            Egyedi hibaoldal
style.css, script.js
robots.txt, sitemap.xml
images/webp/…       használt képek (oldalankénti mappák)
images/originals/…  eredetik (.gitignore-ban, nem kerülnek fel)
pdf/                letölthető dokumentumok
data/*.csv          a Táblázatokból utoljára letöltött pillanatképek (+ keepalive.txt)
tools/*.py          a Táblázat → HTML generátorok
.github/workflows/sync-sheets.yml
drafts/             kész, de nem publikált anyagok (.gitignore-ban): adatkezeles.html
```

- **Menü:** Főoldal · **Események ▾** (lenyíló: Programok = `programok.html`, Naptár = `naptar.html`, Tábor = `tabor.html`) · Csapatotthonunk · Rólunk · **Pénzügyek ▾** (lenyíló: `penzugyek.html#tagdij`, `#nagytabor`, `#kcstabor`, valamint `eszkozok.html`; `ul#subFinance` – az Eszközbérlés a tulajdonos kérésére került ide, a menü rövidítése miatt) · [Csatlakozom] · [Támogass minket]. A lenyíló `li.has-sub` > `button.nav-sub-toggle` + `ul.sub-nav`; az aktuális aloldalnál a `li` `is-current` osztályt, a link `aria-current="page"`-et kap. Egérrel használt széles képernyőn (`@media (hover: hover) and (min-width: 1281px)`) csak rámutatásra (és Tab-fókuszra) nyílik, nyíl nélkül, a kattintás ott szándékosan nem csinál semmit (a tulajdonos kérése); telefonon/érintőképernyőn kattintásra, nyíllal, a hamburger menüben behúzva; a JS (`script.js` eleje) kezeli a nyitást, a kívül kattintást és az Esc-et; menüpontra kattintva a hamburger és a lenyíló is bezárul (az azonos oldali fül-linkeknél is).
- **A fejléc és a lábléc minden HTML fájlban külön szerepel** (12 oldal + 404). Menü-/lábléc-módosítást mindenhol át kell vezetni; utána `diff`-eld az oldalakat.
- **Jekyll-csapda:** a GitHub Pages figyelmen kívül hagyja az `_`-lal kezdődő mappákat. Ezért `images/webp`, `images/originals`, `drafts` (korábban `_webp` stb. volt, a képek emiatt nem látszottak). **Soha ne nevezz el mappát `_`-lal.** `.nojekyll` nincs és nem kell.
- **Cache-bust:** a HTML-ek `style.css?v=116` és `script.js?v=73` formában hivatkoznak a fájlokra (az utolsó ismert állapot). Bármely CSS/JS módosítás után **minden HTML-ben emeld a számot** (`sed`-del vagy ciklussal), különben a böngésző/CDN a régit mutatja.

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
1. Az adatok **három Google Táblázatban** vannak, mindegyik **egészben, Excel (.xlsx) formátumban** közzétéve („Közzététel a weben” → Teljes dokumentum → Microsoft Excel), mindegyikben egy Leírás (útmutató) lappal:
   - **„Csapat adatai”** (szűk kör szerkeszti; `TEAM_SHEET_URL`): Csapatvezetés · Rajok · Számlálók · Táborok
   - **„Vezetői táblázat”** (minden vezető szerkeszti; `LEADERS_SHEET_URL`): Programok · Értesítők · Eszközök · Eszközök kapcsolattartója
   - **„Pénzügyek”** (`FEES_SHEET_URL`): Tagdíj · Nagytábordíj · Kcs tábordíj (blokkos lapok, lásd 4.12)
   A szkriptek a **lapnév** alapján keresnek (a lapokat nem szabad átnevezni), a lap fejlécét pedig az oszlopnevek eleje alapján.
2. A `.github/workflows/sync-sheets.yml` **óránként** (cron `23 * * * *`) és kézzel is (Actions → „Oldal frissítése a táblázatból” → Run workflow) lefuttatja a szkripteket:
   - `tools/sync_programs.py` → `programok.html` és `naptar.html` (`PROGRAMS:START/END`) + programképek a Drive-ról
   - `tools/sync_camps.py` → `tabor.html` (`CAMPS`)
   - `tools/sync_troops.py` → `csatlakozom.html` (`TROOPS`) és `penzugyek.html` (`CUB_CAMP_CONTACTS`: a Kcs tábordíj fül kapcsolata)
   - `tools/sync_notices.py` → **mind a 13 HTML oldal** (`NOTICES`, közvetlenül a `<body>` után), lásd 4.8
   - `tools/sync_counters.py` → `index.html` és `rolunk.html` (`COUNTERS`), lásd 4.9
   - `tools/sync_leaders.py` → `index.html` (`LEADERS`), `csapatotthon.html` (`LEADERS_HOME`), `penzugyek.html` (`LEADERS_FINANCE`) + fotók a Drive-ról
   - `tools/sync_equipment.py` → `eszkozok.html` (`EQUIPMENT`, `EQUIPMENT_CONTACT`), lásd 4.10
   - `tools/sync_fees.py` → `penzugyek.html` (`FEES_MEMBERSHIP`, `FEES_SUMMER_CAMP`, `FEES_CUB_CAMP`), lásd 4.12
   - `tools/sync_gallery.py` → `galeria.html` (`GALLERY`), a többi után
   - közös segédfüggvények: `tools/sync_common.py` (beolvasás, `fetch(args, sheet, book_env)`, `xlsx_sheet_as_csv` – a dátumcellát `ÉÉÉÉ.HH.NN.`, az időcellát `ÓÓ:PP` alakra írja, mint a Google CSV-exportja –, biztonságos letöltés, atomikus írás, `replace_block`); a csomagok pontos verziói: `tools/requirements.txt`.
3. A táblázatok címe a workflow **job-szintű** `env` blokkjában van; a régi, lapokénti CSV-közzétételeket a kód már nem használja (visszavonhatók). Helyi teszt: `python3 tools/sync_troops.py --xlsx "Csapat adatai.xlsx"` (a közzétett fájl letöltve), vagy egy lap CSV-exportjával `--file x.csv`; a Pénzügyeknél `python3 tools/sync_fees.py --file p.xlsx`. A kiinduló fájlok a repón kívül: `../csapat-tablazat/`, `../vezetoi-tablazat/`, `../penzugy-tablazatok/`.
4. A munkafolyamat a változásokat (`*.html data/` és a képmappák) `github-actions[bot]` néven commitolja „Oldal frissítése a táblázatból” üzenettel; ha közben valaki pusholt, rebase-el és legfeljebb háromszor újrapróbálja. Utána a Pages újraépít.
5. Havonta egy apró „életjel” (`data/keepalive.txt`, `date +%Y-%m`) készül, mert a GitHub 60 nap tevékenység nélkül leállítja az ütemezett workflow-t.

### 4.2 Késleltetések (amiket a felhasználónak el kell mondani)
Táblázat mentése → Google CSV-gyorsítótár ~5 perc → a következő óránkénti futás (vagy kézi indítás) → Pages build ~1–3 perc → böngésző/CDN gyorsítótár akár 10 perc. Tehát egy módosítás akár ~egy óra alatt jelenik meg; sürgős esetben kézzel kell indítani a workflow-t. A Google Táblázat automatikusan ment, külön mentés nem kell.

### 4.3 Hibakezelés
- Hibás egyedi sort a szkript kihagy, és figyelmeztetést ír (`::warning::`).
- Ha a CSV nem érhető el, a fejléc elromlott vagy nincs érvényes sor, a szkript **hibával leáll és nem módosít semmit** → az oldal az utolsó jó állapotot mutatja; a futás pirosan jelenik meg az Actions fülön.
- A fejlécet a szkript az oszlopnevek **eleje alapján** (kisbetűsen) keresi, így apró átfogalmazás nem töri el, de az oszlop törlése/átnevezése igen (kötelező: Név, Kezdő dátum, Megjelenjen?).
- A következő workflow-lépések `if: !cancelled()` miatt egy hibás lap esetén is lefutnak.
- A kártyákat a szkript HTML-escape-eli; az e-mail címeket ellenőrzi (érvénytelent kihagy).
- Helyi kipróbálás: `python3 tools/sync_camps.py --file valami.csv` vagy `--xlsx tabla.xlsx`; a repo tartalmát módosítja, ezért utána `git diff`.

### 4.4 Programok lap
Oszlopok: Név · Kezdő dátum · Befejező dátum (ha több napos) · Kezdő idő · Befejező idő · Időpont megjegyzése (pl. gyülekező) · Helyszín · Leírás · Kapcsolattartó 1 neve · Kapcsolattartó 1 e-mail · Kapcsolattartó 1 telefonszám (opcionális) · Kapcsolattartó 2 neve · Kapcsolattartó 2 e-mail · Kapcsolattartó 2 telefonszám (opcionális) · Facebook-esemény linkje · Beszámoló (utólag, hogy milyen volt) · Képek (mappanév a Képek/Program képek-en belül) · Megjelenjen? (A régi, közös „e-mail vagy telefon” oszlopba írt telefonszámot is felismeri.) **Kapcsolattartó kötelező (a tulajdonos kérése, az emlékeztető levelek miatt):** a még véget nem ért programoknál legalább az 1. kapcsolattartó neve és érvényes e-mail címe kell, és ha a 2. kapcsolattartónak van neve, e-mail címe is; ennek hiányában a program nem jelenik meg (figyelmeztetéssel). A már lezajlott programokat nem ellenőrzi (`missing_contact_email`). Tervben: emlékeztető levelek a kapcsolattartóknak (24 órával a kezdés előtt képek; a vége után 1 nappal és 1 héttel beszámoló, ha a Beszámoló oszlop még üres; a képeket nem ellenőrzi, de a levél kéri a feltöltésüket is) – a levélszövegek egyeztetés alatt.
- Kártya sémája: dátum-címke, cím, leírás (a Facebook-esemény linkje a leírás végén „Részletek a Facebook-eseményen” hivatkozásként), `Helyszín`, `Időpont`, „Kérdés esetén keresd:” blokk. Ha nincs kapcsolattartó, a `script.js` a `#newsGrid` `data-default-contact-name/-email` értékét írja be (jelenleg a programokért felelős csapatparancsnok-helyettes).
- A kártyák `id`-je név+dátum alapú slug (pl. `cserkeszmise-20261011`), `data-date` ISO dátummal.
- Dátumformátum a Táblázatban: `2026.10.11.`.
- **Lejárat → Program Archívum (a `script.js` `updateNews()`):** az esemény (utolsó) napja után a kártya a `#newsGrid`-ből átkerül a „Program Archívum” sávba (`#archiveGrid`, `section#archivum`, a közelgők és a naptár között), a legfrissebb elöl; a sáv rejtve marad, ha nincs lejárt program. Nem rejtődik el idővel (a régi `data-keep-days` megszűnt). Mindkét sáv lapozható (`initNewsCarousel(...)` kétszer). A naptár mindkét rácsból olvas. Az archív kártyák nem kapnak megosztás/Naptárba gombot. Teszt a konzolban: `updateNews(new Date('2026-10-12T10:00:00'))`. JS nélkül minden kártya a közelgők között látszik.
- **Naptár külön oldalon (`naptar.html`):** a `sync_programs.py` ugyanazokat a kártyákat a `naptar.html` rejtett `#calendarSource` blokkjába is beírja (ugyanaz a `PROGRAMS:START/END` jelölőpár); a naptár (`initCalendar`) a `#newsGrid`, `#archiveGrid` és `#calendarSource` kártyáiból olvas. A Naptár oldalon az `updateNews()` nem rendez, csak a lejárt-állapotot (`applyPastState`: beszámoló, Facebook-link) és az alapértelmezett kapcsolattartót állítja be; a közelgő kártyák megkapják a megosztás/Naptárba gombokat. A megosztott üzenet és a Google Naptár link mindig a `programok.html#<id>`-re mutat (`programsUrl`).
- **Beszámoló:** a kártyába a leírás (`.news-text.news-desc`) és – ha van – a beszámoló (`.news-text.news-report`, alapból `hidden`) is bekerül; a Facebook-link csak a leírás végén van (`span.news-fb`), és az archívumban az is elrejtődik. Az `updateNews()` az archívumba kerülő kártyáknál a leírást elrejti és a beszámolót mutatja (beszámoló nélkül marad a leírás); a felugró ablak és a naptár másolatai ezt az állapotot öröklik. A Google Naptár link a leírás első bekezdését használja (`.news-desc p`).
- **Programképek (`tools/program_images.py`):** a „Képek” oszlopban megadott mappa (`Képek/Program képek/<mappa>`, a „Program képek/csm” alak is jó) minden képe a kártya **aljára** kerül (a szövegek és a kapcsolattartó után, az „Üzenet másolása” fölé; `.news-gallery[data-gallery]` > `.news-gallery-track`): egyszerre **2 kép** látszik egységes 3:2-es keretben, **vágás nélkül** (`object-fit: contain`), több kép esetén két oldalt nyilakkal (`.gallery-btn`) képenként lapozható (képindex szerint lép, a nyilak állapota kattintáskor azonnal frissül; eseménydelegálással a naptár másolt kártyáin is működik); kattintásra a nagyító nyílik, a program képei között lapozva (a nagyító eseménydelegálással működik, így a naptár másolt kártyáin is). Tárolás: `images/webp/programok/<mappa-slug>/<kép>.webp` (≤ 1400 px) és `…/thumb/<kép>.webp` (≤ 480 px); több program ugyanazt a mappát használhatja (a képek egyszer tárolódnak). Legfeljebb 40 kép/mappa. Csak a változottakat tölti le (`data/program_images.json`); a már nem használt mappák képei törlődnek. Nem található mappa → nincs kép (figyelmeztetés). Kulcs nélkül a meglévők maradnak. Helyi teszt: `DRIVE_LOCAL_DIR=./kepek python3 tools/sync_programs.py --file p.csv` (a `kepek/Program képek/<mappa>/` szerkezettel).
- **Programvideók:** a programmappába tett videókat (`video/*`) a `program_images.py` NEM tölti le: csak a Drive-azonosítójuk (`data-video` a kártya `<img>`-jén) és egy előnézet kerül a repóba – a Drive automatikus bélyegképéből (`thumbnailLink`, `=s1600`), a kártyán lévő kis változaton Pillow-val rajzolt lejátszás ikonnal; ha a Drive még nem készítette el, zöld csempe, és a következő futások újrapróbálják (`"poster": false` az állapotban). A felugró ablakban a videó csempe (`button.program-modal-video`) kattintásra a `https://drive.google.com/file/d/<id>/preview` iframe-re cserélődik (a Google-höz csak ekkor kapcsolódik az oldal); bezáráskor a galéria ürül, a lejátszás leáll. A nagyító a `[data-video]` képeket kihagyja. A videókat a Drive lejátszója szolgálja ki (nem a GitHub), ezért a repó nem nő; nagyon népszerű videónál a Drive átmenetileg korlátozhatja a lejátszást.
- **Programkártya nagyítva (`script.js` `initProgramModal`):** a kártyára kattintva (közelgők, archívum, naptár alatti másolat) felugró ablak nyílik (`.program-modal`, z-index 180): bal oldalt (telefonon felül) a kártya szövegei és gombjai (klónozva, a képsáv nélkül; a szövegrész `article.news-card`, hogy a megosztás gomb működjön), a fő helyen a képek nagy változata többoszlopos (`columns: 3 220px`, telefonon 2), fel-le görgethető, vágás nélküli galériában (`.program-modal-gallery[data-gallery]`). A galéria képére kattintva a nagyító nyílik az ablak fölött (a nagyító `SELECTOR`-a a `.program-modal-gallery img`-t tartalmazza, a kártya bélyegképeit nem – azok az ablakot nyitják, annál a képnél). Linkek, gombok, lapozónyilak nem nyitják az ablakot. Esc: előbb a nagyítót, aztán az ablakot zárja; a nagyító bezárásakor a görgetés zárolva marad, ha az ablak nyitva van. Kép nélküli programnál keskeny, csak szöveges ablak (`.no-images`).
- Időpont nélküli program egész napos eseményként kerül a Google Naptárba.
- A kártyákon „Hozzáadás Google Naptárhoz” gomb és megosztási ablak van (a script `buildCalendarLink`, `buildShareMessage`). A WhatsApp/Messenger közvetlen megosztás **szándékosan ki lett véve** (az Apple/WhatsApp asztali megosztás csak a linket küldi el); marad az „Üzenet másolása” gomb.
- A naptár fix magasságú, a hírdobozok sorban léptethetők, kerek nyilakkal mindkét oldalon; letiltott nyíl elhalványul.
- A „Közelgő programok” fül telefonon (≤ 768 px) a képernyő alján, teljes szélességű kártyaként jelenik meg (asztalon jobbra fent), így nem takarja a nyitókép címét; a hosszú lista a kártyán belül görget.

### 4.5 Táborok lap
Oszlopok: Név · Rövid leírás · Időpont (szabad szöveg) · Helyszín · Főszervező 1–3 (név, e-mail, telefon) · Megjelenjen?
Jelenleg két tábor: **Kiscserkésztábor** (5 nap, most 4. osztályt végzőknek) és **Nagytábor** (az 5. osztályt végzők 6 napra jönnek, mindenki más 10 napra). Időpont/helyszín: „Hamarosan frissítjük!” amíg nincs megadva. Az e-mailek és telefonszámok opcionálisak, bármelyik kombináció kezelt.

### 4.6 Rajok lap
Oszlopok: Raj neve · Indulás éve (a tanév kezdő éve, amikor a raj 4. osztályos volt) · Jelenlegi osztály (automatikus, ne írd át) · Rajparancsnok 1–3 (név, e-mail, telefon) · Megjelenjen?
- A **„Jelenlegi osztály” oszlop a Táblázatban képlet**, de az oldal nem erre támaszkodik: a `script.js` `updateGrades()` minden megnyitáskor kiszámolja az osztályt az „Indulás éve” alapján, így a **szeptember 1-jei léptetés magától megtörténik** (a kártyák `data-grade` és `data-school-year` attribútumot hordoznak). A 9. osztályba lépett raj eltűnik (4–8. látszik); ha egy osztályhoz nincs raj, „Hamarosan frissítjük!” felirat áll.
- Új 4. osztályos raj: új sor a Táblázatban, jövőbeli indulási évvel előre is felvehető (addig rejtve marad).
- **Pénzügyek, Kcs tábordíj fül:** a fül alján kapcsolatként a 4. osztályos raj rajparancsnokai állnak (a tulajdonos kérése), nem a pénzügyi felelős. A `sync_troops.py` minden raj rajparancsnokait a `penzugyek.html` `CUB_CAMP_CONTACTS` blokkjába is beírja, a vezetőkéhez hasonló személykártyán (`person_card.py`, szerep: „Rajparancsnok”, fotó nincs → monogram; rajonként egy `.fee-troop[data-school-year]` csoport, osztály-felirat nélkül); a `script.js` `updateCubCampContact()` csak a most 4. osztályost mutatja (szeptember 1-jén magától vált). Ha nincs 4. osztályos raj, a Kcs fülön is a pénzügyi felelős látszik. A kapcsolat-blokkok: `.fee-contact[data-for]`, fülváltáskor az `initFeeTabs` kapcsolja őket.

### 4.7 Ha a Táblázat átszervezése kell
Új lap hozzáadása = új lap a megfelelő közös táblázatban + új szkript a `sync_common.py` mintájára (`common.fetch(args, '<lapnév>', book_env=…)`) + új marker-pár a célfájlban + új lépés a workflow-ban (és ha új mappát ír, a `git add` sor kiegészítése).

### 4.8 Értesítők (piros sáv az oldal tetején)
Külön, nyilvános Google Táblázat (útmutató lappal; a táblázatok a tulajdonos Google Drive-ján vannak, xlsx-másolatot a repóban nem tartunk). Oszlopok: Cím · Mettől · Meddig · Határidő · Üzenet · Megjelenjen? (kötelező: Cím, Üzenet, Megjelenjen?). Tipikus tartalom: tagdíjfizetési, tábori jelentkezési határidő.
- A szkript minden oldal `<body>`-ja utáni `NOTICES` blokkjába `.notice` elemeket ír `data-from`, `data-until` (üres Meddig esetén a Határidő) és `data-id` (a cím+üzenet+határidő SHA1-ének eleje) attribútummal, **alapból `hidden`**. A Meddig/Határidő alapján már lejárt sor ki sem kerül. Üres lista megengedett (nem hiba, mint a többi lapnál).
- A `script.js` `updateNotices()` mutatja a ma érvényeseket (a Meddig napja még beleszámít). A × gomb a `data-id`-t a **`sessionStorage`** `closedNotices` kulcsába menti (a tulajdonos kérése): az oldalon belüli lapozás és a vissza gomb alatt rejtve marad, de **újratöltéskor** (`performance.getEntriesByType('navigation')[0].type === 'reload'` → a kulcsok törlődnek) és a böngészőlap bezárása/újranyitása után újra megjelenik. Ugyanez a főoldali „Közelgő programok” fülre (`upcomingTabClosed`; közös `readDismissed`/`addDismissed`). A fül a ma és a következő 7 napban kezdődő vagy épp tartó programokat mutatja. A régi `localStorage` `closedNotices` maradványát a script törli. Teszt: `updateNotices(new Date('2026-11-16T10:00:00'))`.
- A sáv a ragadós fejléc fölött van, és elgörgethető. A főoldali „Közelgő programok” fül (`initUpcomingTab`) emiatt a fejléc alja alá igazodik (görgetéskor visszaáll 90 px-re).
- Új oldal létrehozásakor a `<body>` utáni `NOTICES` jelölőpárt is másold át, és vedd fel a `PAGES` listába a `sync_notices.py`-ban.
- Helyben a macOS-es Python letöltéskor SSL-hibát adhat (hiányzó tanúsítványok); ilyenkor `curl`-lel töltsd le a táblázatot, és `--xlsx`-szel futtasd (vagy `SSL_CERT_FILE` a rendszer gyökértanúsítványaival). Az Actionsben nincs ilyen gond.

### 4.9 Számlálók (Tag / Raj / Őrs)
Külön, nyilvános Google Táblázat. Oszlopok: Felirat · Szám · Megjelenjen? (mind kötelező fejléc). Minden sor egy kártya, a sorrend a kártyák sorrendje; a dizájn 3 kártyára készült.
- Helyük: a főoldalon a „Csapatunk” bekezdés és a „Tovább a Rólunk oldalra” gomb között (zöld háttéren fehér kártyák); a Rólunkon a „Csapatunkról” h2 alatt, a `.prose`-on belül, az első h3 előtt – az `initSplitBlocks()` az első h3 előtti elemekhez nem nyúl, ezért ott biztonságos.
- A HTML-ben a végső szám áll (`data-count` is). A `script.js` `initCounters()` a számjegyeket 0–9-es, függőleges „szalagokra” cseréli (2 teljes kör + a célszámjegy), és IntersectionObserverrel, egyszer tekeri fel őket. A cella magassága a `--odo-h` CSS-változó (`.stat-number`), a JS is ezzel tol.
- A számok betűje szándékosan **nem Georgia** (annak „régies”, eltérő magasságú számjegyei gördülés közben ugrálnak), hanem Times New Roman / Noto Serif.
- Nincs megjelenő sor → a szkript hibával leáll, az oldal változatlan marad.

### 4.10 Eszközbérlés
Külön nyilvános Google Táblázat két, külön közzétett lappal: **Eszközök** (Eszköz · Darabszám · Megjegyzés (pl. méret) · Megjelenjen?) és **Kapcsolattartó** (Név · Szerep · E-mail · Telefon · Megjelenjen?).
- A `sync_equipment.py` mindkét lapot beolvassa (helyben `--xlsx`, vagy `--file` és `--contact-file`). Üres darabszámnál nincs „db” címke; nincs megjelenő eszköz → hiba, az oldal változatlan. Nincs kapcsolattartó → figyelmeztetés, és a 802@cserkesz.hu kerül az oldalra. A kapcsolattartók a főoldalihoz hasonló személykártyát kapnak (`person_card.py`, fotó a Drive-ról, lásd 6. pont).
- Az e-mail mellé **ne generálj másolás gombot**: a `script.js` minden mailto link mellé magától tesz egyet (különben kettő lesz).
- A bevezető szöveg (a tulajdonos kérésére úgy fogalmazva, hogy kiderüljön: nem ingyenes, de a „pénz/díj” szó nem szerepel) az oldalon kézzel szerkeszthető.
- Az oldal a menü Pénzügyek lenyílójának utolsó pontja („Eszközbérlés”); ott a lenyíló `is-current`. Az Eszközbérlés a Pénzügyek lenyílóba került, így a hamburgerre váltás határa **1280 px** (`@media (max-width: 1280px)`, a `script.js` `hoverMenu`-jében és a hover-szabályban `min-width: 1281px`); a menü+logó kb. 1250 px-et igényel. Újabb menüpontnál mérd újra.

---

### 4.11 Galéria (`galeria.html`)
A `tools/sync_gallery.py` a `GALLERY:START/END` blokkot írja (óránként, a programok után fut). Szakaszok: **Programjaink** (a `data/programs.csv` és a `data/program_images.json` alapján mappánként, a program nevével és legutóbbi dátumával, a legfrissebb elöl; képek és videók), **Tábor** (`images/webp/tabor/`), **Csapatotthonunk** (`csapatotthon/`), **Csapatunk** (`fooldal/` + `rolunk/`). Kimarad: `kozos/` (vezetők portréi, logók, piktogramok), `tamogass/` (plakát, QR). Az alt szöveget az oldalak `<img>` elemeiből veszi; ahol van `thumb/`, az látszik, a nagyítóban a nagy kép. A rács `columns: 4 220px` (telefonon 2), vágás nélkül; a konténer (`.gallery-page[data-gallery]`) miatt a nagyító az egész galérián végiglapoz, a videók a nagyítóban, kattintásra indulnak. **Új képmappa felvételekor** (pl. új oldal képei) a `STATIC_SECTIONS` listát bővíteni kell. A lábléc minden oldalon tartalmazza a „Galéria” linket.

### 4.12 Pénzügyek (`tools/sync_fees.py`)
**Egyetlen** Google Táblázat (a tulajdonos kérése), lapjai: **Leírás** (útmutató, első lap; az oldal nem olvassa) · **Tagdíj** · **Nagytábordíj** · **Kcs tábordíj** (a lapnév = a fül neve, ez alapján keresi a szkript). A **teljes dokumentum** Microsoft Excel (.xlsx) formátumban van közzétéve (Fájl → Megosztás → Közzététel a weben → Teljes dokumentum, .xlsx), egy cím kell: `FEES_SHEET_URL` (üres → figyelmeztetés, az oldal változatlan). A beolvasáshoz `openpyxl` kell (a workflow telepíti).
Egy fül-lapon egymás alatt négy blokk; a blokkot az A oszlopba írt, egyedül álló blokkcím kezdi (`ALAPADATOK`, `DÍJAK`, `RÉSZLETEK`, `KÖLTSÉGEK`, kis/nagybetű mindegy), a táblázatos blokkoknál a következő sor a fejléc; az üres sorokat kihagyja (a sablonban minden blokk alatt van pár üres sor új tételeknek). Blokkok:
- **ALAPADATOK** (két oszlop, Mező · Érték; a mezőnév eleje alapján): Megjelenés kezdete · Megjelenés vége · Cím · Bevezető szöveg · Kiemelt mondat · Alapüzenet · ECSET kódok linkje · Támogatás űrlap linkje · Támogatás igénylésének határideje (a „Támogatás igénylése” cím alatt, kiemelve; üresen figyelmeztetés; a határidő UTÁNI nap 23:59-kor (a tulajdonos kérése: egy nap türelmi idő) a `.fee-form-open` rész (határidő, szöveg, űrlap, link) eltűnik, az iframe ki is kerül az oldalból, és a helyén a `.fee-form-closed` üzenet áll („A támogatási igények leadási határideje <hónap nap>. volt, …”) – `.fee-form[data-until]` = a határidő napja, `feeFormCloseTime()`, `updateFees()`, nyitva hagyott oldalon időzítővel; a szkript a futás időpontja szerint a `hidden`-t is beállítja. Az űrlap Google-címe ettől még elérhető: a Google Formsban is le kell zárni a válaszadást) · Költségek címe / bevezetője / megjegyzése.
- **DÍJAK**: Kategória · Összeg · Részletezés · Magyarázat címe · Magyarázat · Megjelenjen? (a díjkártyák és alattuk a magyarázó bekezdések egy lapon, külön oszlopokban, egymástól független sorokkal – a tulajdonos kérése).
- **RÉSZLETEK**: Cím · Befizetési határidő · Összeg · Megjegyzés · Megjelenjen?  **KÖLTSÉGEK**: Tétel · Összeg (Ft) · Megjelenjen? (üres blokk → nincs költségek rész). A „Megjelenjen?” oszlopok legördülő listásak (igen/nem).
- **Időszak csak fülszintű** (a tulajdonos kérése): a panel `data-from`/`data-until`-t kap; a `script.js` `updateFees()` ezen belül a tartalmat, kívül (vagy kezdet/cím nélkül) az alapüzenetet mutatja; a sorok egyenként a „Megjelenjen?” = nem-mel rejthetők. A szkript a futás napja szerint a `hidden` attribútumot is beállítja (JS nélkül is helyes).
- Fix, a kódban rögzített (minden fülön azonos): banki adatok, közlemény-figyelmeztetés példával, ECSET doboz szövege, „Támogatás igénylése” szöveg; a táblázatból csak az ECSET- és az űrlaplink jön (https:// kell). A számlaszám szándékosan nem írható át a táblázatból.
- Szöveg: cellán belüli új sor = új bekezdés, `**…**` = félkövér, minden más escape-elve. Puszta szám összegnél → „15 000 Ft”; dátum `2026.10.01.` vagy valódi dátumcella is jó.
- Nem xlsx fájl → hiba, az oldal változatlan. Hiányzó fül-lap, ALAPADATOK blokk vagy fejléc-oszlop → az adott fül változatlan, a többi frissül, a futás piros. Pillanatkép: `data/fees_membership.json`, `fees_summer_camp.json`, `fees_cub_camp.json`. Helyi teszt: `python3 tools/sync_fees.py --file p.xlsx [--today 2026-03-15]`.
- A kiinduló sablon (a jelenlegi tartalommal) a repón kívül van: `../penzugy-tablazatok/Pénzügyek.xlsx`; a tulajdonos ebből hozza létre a Google Táblázatot.

### 4.13 Biztonság és működésbiztonság (a tulajdonos kérése: „ahol lehet, biztonságosabbra”)
- **Workflow:** az actionök teljes commit-SHA-ra rögzítve (`actions/checkout@…  # v4.4.0`, `actions/setup-python@…  # v5.6.0`), a pip-csomagok pontos verzióra (`tools/requirements.txt`) – frissítés csak tudatosan, helyi teszt után. `timeout-minutes: 20`. Az API-kulcs (`secrets.GOOGLE_API_KEY`) csak a három, képet töltő lépés kapja meg; a Drive-mappa azonosítója nem titok.
- **Táblázatból jövő adat:** minden szöveg HTML-escape-elve kerül az oldalra; a linkek csak engedélyezett címre mutathatnak (`common.safe_url`): Facebook-esemény → facebook.com/fb.me, ECSET-lista → drive/docs.google.com, támogatási űrlap → `https://docs.google.com/forms/…` (más esetben figyelmeztetés, a link kimarad). A naplóüzenetek a cellatartalmat GitHub-módon escape-elik (`%`, CR, LF), így egy cella nem tud workflow-parancsot befecskendezni.
- **Letöltés:** `common.download` – csak https, `User-Agent`, 30 s időkorlát, 30 MB méretkorlát, átmeneti hibánál (hálózat, 5xx, 429) 3 próbálkozás, maradandónál (4xx, SSL) azonnal hiba; a hibaüzenet soha nem tartalmazza a címet (abban API-kulcs lehet).
- **Írás:** minden oldal-, kép- és állapotfájl atomikusan íródik (`common.write_text/write_bytes`: ideiglenes fájl + `os.replace`), így egy megszakadt futás nem hagy félkész fájlt.
- **Törlés:** a programképek mappáit csak az `images/webp/programok/` alatt törli (`_inside_dir`), és ha a Programok lapon nincs „Képek” oszlop (átnevezték/törölték), egyáltalán nem töröl (különben minden programkép eltűnne).
- **Hibás bemenetek (tesztelve):** a „Megjelenjen?” oszlopban a „nem”, „Nem.”, „ NEM ”, „no”, „n”, „hamis”, „0” mind rejt (`common.is_hidden`); hibás vagy a kezdő előtti befejező idő, a Mettőlnél korábbi Meddig (értesítő), a kezdetnél korábbi Megjelenés vége és a nem dátum igénylési határidő (Pénzügyek) figyelmeztetést ad; a számláló csak egész számot vagy hármas tagolást fogad el („4.5” nem lesz 45); a darabszámnál a „2 db” is jó; a Pénzügyek blokkcíme kettősponttal („Alapadatok:”) is felismerhető. A fejlécet a kód az első 5 sorban keresi (`common.find_header`), így egy fölé beszúrt üres vagy címsor nem töri el a frissítést (figyelmeztet). Programoknál a kezdő előtti befejező idő másnapot jelent (éjszakai program, pl. 22:00–02:00), csak az azonos idő elírás. Két, csak ékezetben/írásjelben eltérő Drive-mappanév (azonos tárolási név) és két, ékezet nélkül azonos nevű vezető figyelmeztetést ad (a második nem kap képet/fotót). A workflow `TZ: Europe/Budapest`-tel fut (lejárat, űrlapzárás, szeptember 1. magyar idő szerint), a mentés `git add -A -- '*.html' data images/webp` (egy nem létező almappa nem buktatja el). Egy osztályhoz több raj is tartozhat (a Csatlakozom rács mindet a helyére rendezi). Hibás URL-horgony (pl. `#%zz`) nem állítja meg a szkriptet; a Pénzügyek fülváltás az oldal tetejére ugrik.
- **Vissza gomb (telefon):** a felugró elemek (személy-ablak, program-ablak, nagyító) megnyitáskor egy előzmény-bejegyzést tesznek (`modalHistory.opened`, `history.pushState`), így a Vissza gomb / visszahúzás a legfelső elemet zárja be, nem hagyja el az oldalt; ×, Esc vagy háttérkattintás esetén a bejegyzés is törlődik (`modalHistory.closed` → `history.back()`, a saját popstate-et figyelmen kívül hagyja). Új felugró elemnél ugyanezt kell használni: `open`-ban `if (wasHidden) modalHistory.opened(close)`, a `close(fromHistory)` végén `if (fromHistory !== true) modalHistory.closed(close)`.
- **Böngésző:** minden oldalon `Content-Security-Policy` meta (szkript csak a saját oldalról + a 404.html beágyazott szkriptje sha256-hash-sel; beágyazás csak docs/drive/www/maps.google.com; `object-src 'none'`, `base-uri 'self'`, `form-action 'none'`, `upgrade-insecure-requests`) és `referrer` meta. **Ha a 404.html beágyazott szkriptjét módosítod, a hash-t újra kell számolni** (`sha256` a `<script>` tartalmáról, base64), és mind a 13 oldalon cserélni. Új külső forrás (pl. betűtípus, más beágyazás) csak a CSP bővítésével működik. A beágyazott Google Űrlap, a térkép és a Drive-lejátszó `sandbox` attribútumot kap (nem navigálhatják el az oldalt); a `script.js` csak `https://docs.google.com/forms/` címet tölt az űrlap-keretbe.

## 5. Oldalankénti tudnivalók

- **Főoldal:** hero és „Csapatunk” kép+szöveg (asztalon a 802-es légifotó bal oldalon, telefonon nyitókép; csoportkép a Csapatunk szekcióban), Kapcsolat: kártyák 2 oszlopban telefonon. A kártyákra kattintva **bemutatkozó ablak** nyílik (kép, név, szerep, bemutatkozó szöveg, másolható e-mail, telefon). A szöveg a kártyán belüli rejtett `<div class="person-bio">`-ban van; a kártyákat a `sync_leaders.py` generálja a Csapatvezetés táblázatból (lásd 6. pont). Fotó nélkül monogram látszik (`images/webp/kozos/team/`).
- **Facebook / Instagram:** csak **linkgombok** (802szentkorona; csapatotthon: gdlcserkeszhaz / bezsilla.villa), a tartalom nincs betöltve – így kattintás előtt nincs külső süti/adatátadás. Ne tegyél vissza beágyazott widgetet adatkezelési átgondolás nélkül.
- **Rólunk / Csapatotthonunk:** a fotók az oldal végén a `.side-photos` blokkban vannak; a `script.js` (`initSplitBlocks()`) a szöveget a h3 címek mentén egyenlő részekre bontja, és mindegyik mellé 2–3 fotót tesz váltakozó oldalra (telefonon a szöveg fölé). JS nélkül a fotók rácsban a szöveg alatt látszanak. Új kép = a `.side-photos` blokkba. **Kézi tördelés:** ha a szövegben van `h3.block-start`, a blokkok ezeknél a címeknél kezdődnek (a hossz szerinti automatikus felosztás helyett), a képek egyenlően, sorrendben oszlanak el – a Rólunk „Csapatunkról” része így 3 blokk × 3 kép (bemutatkozás/értékek · év programjai · felépítés + Gödöllő; a tulajdonos kérése). A „Cserkészetről” rész 4 blokk × 3 kép (Kik vagyunk? · Mit csinálunk? · Cserkésztörvény · Fogadalom + Köszöntés és jelszó); a cserkészmódszer-lista, a Cserkészliliom és az Egyenruhánk rész a tulajdonos kérésére kikerült. Az egyetlen álló kép (`img_7826`) a leghosszabb szövegű, utolsó blokkban van. A script egy placeholder megjegyzés-csomópontot (`marker`) használ a darabolásnál – ne cseréld vissza a referencia-csomópont beszúrására (volt `HierarchyRequestError`).
- **Tábor:** fent kártyák (Táblázat), alatta általános információ váltakozó kép+szöveg blokkokkal; a képek `images/webp/tabor/` (nagy) és `tabor/thumb/` (az oldalon látszó bélyeg; kattintásra a nagy nyílik). Letölthető PDF-ek a `pdf/` mappában (felszerelési lista, EU-nyilatkozat, belépési nyilatkozatok).
- **Csatlakozom:** 4.–8. osztályosok, rajparancsnokok kártyái (Táblázat).
- **Csapatotthonunk:** Bezsilla villa, hat fotó (`bezsilla1–6.webp`, kattintásra nagyítható), Google Maps beágyazás, elérhetőség, FB/IG gombok, Grébel Hanna kártya bemutatkozó ablakkal.
- **Támogass minket:** szöveg, SZJA 1% kép (`ado1.webp`), két kártya (egyesület adatai, banki átutalás; adószám/számlaszám **másolás gombbal**), palackvisszaváltás QR-kód (`palack_qrkod.jpg` **szándékosan JPG**, hogy beolvasható maradjon). A szövegben a visszaváltási díj „közvetlenül az egyesület számlájára érkezik” (a tulajdonos kérésére nem szerepel, hogy ki kapja vagy nem kapja).
- **Pénzügyek (`penzugyek.html`):** három fül (`.fee-panel[data-tab]`), **fülsáv nélkül** (a tulajdonos kérésére kivéve): a címbeli `#tagdij`, `#nagytabor`, `#kcstabor` nyitja a fület, azaz a menü Pénzügyek lenyílója; cím nélkül a Tagdíj (a panelek `id`-je `panel-…`, hogy a böngésző ne ugorjon; `script.js` `initFeeTabs`). Minden fül tartalma a táblázatokból jön (4.12), egységes sorrendben: cím + bevezető · kiemelt mondat (`.fee-key`) · díjkártyák (`.price-grid`) · magyarázatok (`.fee-rules`) · részletek egymás alatt (`.fee-items`, a banki kártyákkal egyező szélességben) · fix kártyák (`.fee-pay`: banki adatok, `.fee-warning` példa-közleménnyel, `.fee-ecset`) · költségek (`.fee-costs`, opcionális) · támogatás igénylése beágyazott Google Űrlappal (`.fee-form`; az iframe `src`-jét az `initFeeTabs` csak akkor tölti be a `data-src`-ből, amikor a fül és az időszakos tartalma (`.fee-content`) is látszik). Mindenhol „ECSET kód” a kifejezés (a tulajdonos kérése). Az ECSET kódok szándékosan nincsenek az oldalon, csak a szülőkkel megosztott Drive-fájl linkje. **TESZT:** a nagytábor határidői és időszaka kitaláltak (nov. 30., dec. 31.; időszak 2026-10-01 – 2026-12-31), a valódiak: 2026.05.31. és 2026.06.30. A Kcs tábordíj fülön csak az alapüzenet van. Alul a kapcsolat: a Tagdíj és a Nagytábordíj fülön a pénzügyi felelős (`LEADERS_FINANCE`), a Kcs tábordíj fülön a 4. osztályos raj rajparancsnokai (`CUB_CAMP_CONTACTS`, lásd 4.6).
- **Másolás gombok:** kis, ikon-stílusú gombok minden e-mail mellett (kivéve a láblécben és az eseménykártyákon).
- **Dokumentumok:** a `pdf/` fájljai; csak a láblécből érhető el.
- **404.html:** egyedi hibaoldal.
- **SEO:** `robots.txt`, `sitemap.xml` (jelenleg `YOUR-DOMAIN-HERE`), `share.jpg` (1200×630) megosztási kép, JSON-LD logó: `logo_white.jpg`.

---

## 6. Képek

- Új kép: eredeti → `images/originals/<oldal>/`, WebP (kb. 1000–1600 px széles, minőség ~80) → `images/webp/<oldal>/`, és abból hivatkozz. Hero ~1600 px, személyfotó ~400 px elég.
- Kivétel: QR-kód JPG, megosztási kép JPG.
- A kép betöltési hibáját a `script.js` kezeli (hiányzó kép nem töri el az elrendezést).
- **Vezetők kártyái és a személyfotók a Google Drive-ról (`tools/sync_leaders.py` + `tools/drive_photos.py`):** a „Csapatvezetés” táblázat (Név · Szerep · Bemutatkozás (rövid szöveg) · E-mail (egy) · Telefon · Fotó (fájlnév) · Megjelenjen?) adja a főoldal `LEADERS` blokkját; akinek a szerepében a „Csapatotthon” szó szerepel, az a `csapatotthon.html` `LEADERS_HOME` blokkjába (12 szóközös behúzással; a `.home-visit` rács jobb oszlopában, balra mellette a portyázó csapatoknak szóló kártya a „Csapatotthon kisokos” letöltés gombbal: `pdf/csapatotthon_kisokos.pdf`; telefonon egymás alatt), akinek a „Pénzügy” szó, az a `penzugyek.html` `LEADERS_FINANCE` blokkjába is bekerül. A felugró ablak fejlécében a név és a szerep áll (`person-bio-role`), alatta a „Bemutatkozás” (`person-bio-text`, a cellán belüli sortörések megmaradnak), majd az e-mail és a telefon. A „Miért keresd?” lista megszűnt. A „Fotó” oszlopot a kód a régi „Fájlnév…” fejléccel is felismeri (`read_table` több előtagot is elfogad tuple-ként). Ha van telefonszám, a kártyán az e-mail alatt (`a.person-phone`, `tel:` link) és a felugró ablakban is megjelenik (a tulajdonos kérése; minden `person_card.py`-s kártyára: főoldal, Csapatotthonunk, Pénzügyek, Eszközbérlés). A **Fotó** a Drive „Képek” mappájában lévő fájl neve kiterjesztéssel; a `drive_photos.py` a Drive API-val (nyilvános mappa + API-kulcs) a Képek gyökerében és almappáiban (pl. `Csapatvezetés/`; a `Program képek/` kivételével) név szerint megkeresi (kis/nagybetű nem számít; azonos névnél a legutóbb módosított), letölti, EXIF szerint elforgatja, kicsinyíti (≤ 400/600 px), és WebP-be menti: `images/webp/kozos/team/<név-slug>.webp` (pl. `cseri-holzman-lili.webp`). Csak a változottakat tölti le (`data/photos.json`). **Üres fájlnév, a mappában nem található vagy nem kép fájl → monogram** (a régi `<név-slug>.webp` törlődik; a tulajdonos kérése). Átmeneti letöltési hibánál a régi fotó marad. **Kulcs nélkül** (`GOOGLE_API_KEY` hiányzik) a kártyák generálódnak, a fotók nem frissülnek (figyelmeztetés, zöld futás). A kártya HTML-jét a `tools/person_card.py` állítja elő; ugyanezt (és a fotókezelést) használja a `sync_equipment.py` is: az Eszközbérlés minden kapcsolattartója ilyen személykártyát kap (Kapcsolattartó lap „Fájlnév” oszlopa), kattintásra felugró ablakkal. Régi személyek fotói nem törlődnek automatikusan (kis fájlok, kézzel törölhetők). Helyi teszt: `DRIVE_LOCAL_DIR=./kepek python3 tools/sync_leaders.py --file v.csv`. A workflow-ban: `TEAM_SHEET_URL`, `DRIVE_IMAGES_FOLDER_ID` (job-szinten), és `GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}` (**GitHub Secret**, csak a Drive API-ra korlátozva). **A korábban a csevegésben kiszivárgott kulcsot törölni kell, és soha nem szabad kulcsot fájlba/repóba/csevegésbe írni.** PDF-mappa: később, ugyanezzel a mintával.

---

## 7. Ismert buktatók

1. `_` kezdetű mappa → a Pages nem szolgálja ki (lásd 2. pont).
2. CSS/JS változtatás után elfelejtett `?v=` emelés → a felhasználó a régit látja.
3. A robot-commitok miatt „divergent branches”: `git pull` (rebase) push előtt.
4. A `programok.html`, `tabor.html`, `csatlakozom.html` marker közötti része, valamint minden oldal `NOTICES` blokkja **minden szinkronnál felülíródik** – kézi szerkesztés elvész. Az oldal többi része szerkeszthető.
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
- **Fotószinkron élesítése** (6. pont): új, Drive API-ra korlátozott API-kulcs a GitHub Secretsbe (`GOOGLE_API_KEY`); a régi, kiszivárgott kulcs törlése. Amíg nincs kulcs, a vezetők kártyái frissülnek, a fotók nem. PDF-ek Drive-ról: később.
- Lehetséges bővítések, amiket felajánlottunk: a Programok lapon külön e-mail/telefon oszlop; „Szövegek” és „Beállítások” lap a Táblázatban (szöveges blokkok soronként egy bekezdéssel, linkek/térkép a Táblázatból); a felugró „Közelgő programok” fül telefonos átfedésének javítása; a workflow-ban használt action-verziók frissítése (`actions/checkout@v4`, `setup-python@v5`).
- **Függő helyi módosítások:** a legutóbbi munkamenet végén vannak commitolatlan változások; ellenőrizd `git status`-szal, és a tulajdonos döntse el, mikor commitol/pusholja.

---

## 9. Munkamódszer-ajánlás új agentnek

**Nyelvi szabály (a tulajdonos kérése):** a kód és a kommentek **angolok** (változó-, függvény- és fájlnevek, HTML-jelölők, workflow-változók, CSS/JS/Python/HTML-kommentek). **Magyar marad:** minden, ami az oldalon megjelenik; a szinkronszkriptek napló- és hibaüzenetei, valamint a workflow lépésnevei és commit-üzenetei (ezeket a táblázatot szerkesztő vezetők olvassák); a táblázatok fejlécei és lapnevei, amelyek alapján a kód keres; és a linkek (oldalfájlok, képmappák, `#tagdij`-féle horgonyok). Ez a dokumentum és a README magyar.

1. Olvasd el a `README.md`-t és ezt a fájlt, majd `git status` / `git log --oneline | head`.
2. Módosítás előtt helyi szerverrel (`python3 -m http.server`) nézd meg asztali és telefonos szélességben (≈375 px).
3. Táblázat-eredetű szakaszhoz ne nyúlj kézzel; a szkriptet vagy a Táblázatot módosítsd.
4. Minden CSS/JS változás után emeld a `?v=` számot az összes HTML-ben.
5. Kis, célzott módosításokat végezz; a tulajdonos gyakran finomít (képek elrendezése, szövegek), és kifejezett, konkrét vizuális elvárásai vannak (3. pont).
6. Soha ne kérj/írj be kulcsot, jelszót a repóba; a titkok a GitHub Secrets-ben vannak.
7. Commitot/pusht csak kérésre.
