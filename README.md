# 802. sz. Szent Korona Cserkészcsapat – weboldal

Statikus (HTML/CSS/JS) többoldalas weboldal, backend nélkül, GitHub Pages-en közvetlenül publikálható. Csak magyar nyelvű.

## Fájlstruktúra

- `index.html` – Főoldal (borítókép + név, Csapatunk (kép + szöveg), Kapcsolat, Facebook- és Instagram-gombok)
- `rolunk.html` – Rólunk (két pont: Csapatunkról, Cserkészetről; a szöveg a csapat korábbi honlapjáról, a 802szentkorona.hu-ról származik)
- `tabor.html` – Tábor (kiscserkésztábor és nagytábor kártyák, általános információk váltakozó kép + szöveg blokkokkal; a képek az `images/webp/tabor/`, a letölthető PDF-ek a `pdf/` mappában)
- `dokumentumok.html` – Dokumentumok (a `pdf/` mappa letölthető fájljai; a lábléc linkelte, a menüben nincs)
- `csatlakozom.html` – Csatlakozom (4.–8. osztály, rajparancsnokok)
- `csapatotthon.html` – Csapatotthonunk (Bezsilla villa, elérhetőség, Google Maps, Facebook- és Instagram-gombok)
- `programok.html` – Programok (hírdobozok léptethető sorban + naptár)
- `tamogass.html` – Támogass minket (adó 1%-os kép, egyesület adatai, számlaszám)
- `penzugyek.html` – Pénzügyek (Tagdíj / Nagytábordíj / Kcs tábordíj fülek; a menüben „Pénzügyek ▾” lenyíló)
- `style.css`, `script.js` – közös kinézet és működés (mobil menü, hiányzó képek kezelése)
- `robots.txt`, `sitemap.xml` – Google-kereshetőséghez

A fejléc és a lábléc mind a 7 HTML fájlban külön szerepel – ha módosítod a menüt vagy a láblécet, **mind a 7 fájlban** át kell vezetni.

## Képek

Minden kép az `images/` mappában van, két fő mappára bontva, azon belül oldalak szerint:

- **`images/webp/`** – az oldalon használt, tömörített képek (WebP; a QR-kód és a megosztási kép JPG):
  - `fooldal/` – `csapatunk.webp` (a főoldali borítókép, csoportkép; levágva a csoport körül), `hero.webp` (a 802-es légifotó; asztalon a Csapatunk szekció bal oldala, telefonon a nyitókép)
  - `rolunk/` – a Rólunk oldal fotói (a szöveg két oldalán)
  - `tabor/` – a Tábor oldal képei (nagy változat) és `tabor/thumb/` (kis bélyegkép, ez látszik az oldalon; a nagy kattintásra nyílik meg)
  - `csapatotthon/` – `bezsilla1.webp` … `bezsilla6.webp` (a Csapatotthonunk oldalon a szöveg két oldalán, keskenyen a tetején 2 oszlopban; kattintásra nagyítható)
  - `tamogass/` – `ado1.webp` (adó 1%-os kép), `palack_qrkod.jpg` (palackvisszaváltás QR-kód: szándékosan JPG, hogy beolvasható maradjon)
  - `kozos/` – több oldalon használt képek: `logo_white.webp` / `logo_white.jpg` (fejléc, ill. strukturált adat logója), `logo_green.jpg` (favicon), `share.jpg` (megosztási előnézet, 1200×630), `team/` (a kapcsolati kártyák fotói; amíg nincs fotó, monogram látszik)
- **`images/originals/`** – az eredeti, tömörítetlen fotók ugyanilyen oldalankénti bontásban. Ezt a `.gitignore` kizárja, nem kerül a GitHubra.

Új kép felvétele: tedd az eredetit az `originals/<oldal>/` mappába, készíts belőle WebP-t (kb. 1000–1600 px széles, minőség ~80) az `webp/<oldal>/` mappába, és abból hivatkozz. A borítókép ~1600 px széles, a személyek fotói ~400 px elég, különben lassul az oldal.

## Színek

A `style.css` elején lévő `:root` blokkban vannak (386641, 6a994e, a7c957 az alap, a háttér- és szegélyszínek ezekből levezetettek). Elég ezeket átírni.

## Karbantartás

- **Események menü, Program Archívum, programképek:** a fejlécben az „Események” lenyíló alatt van a Programok (`programok.html`: közelgő programok és archívum), a Naptár (`naptar.html`) és a Tábor. A lejárt programok a böngészőben automatikusan átkerülnek a „Program Archívum” sávba (a közelgők és a naptár között), és ott a leírás helyett a táblázat „Beszámoló” oszlopának szövege látszik (ha van). A programok táblázatának „Képek” oszlopában megadott Drive-mappa (Képek és videók/Program képek/<mappa>) képei és videói a kártyára kerülnek (`tools/program_images.py`); a kártyára kattintva felugró ablak nyílik többoszlopos galériával, a képekre kattintva nagyító, a videókra kattintva a Drive lejátszója indul (a videókat nem tároljuk a repóban). A Drive „Képek és videók” mappa szerkezete: `Csapatvezetés/` (személyfotók), `Program képek/<mappa>/` (programképek és -videók; bármely „Program…” kezdetű név jó).
- **Galéria (`galeria.html`, a láblécből):** az oldal összes fotója és videója szakaszokba rendezve (Programjaink, Tábor, Csapatotthonunk, Csapatunk), a vezetők portréi, a logók és a plakátok nélkül. A `tools/sync_gallery.py` állítja össze, óránként frissül; kattintásra nagyító nyílik.
- **Az adatok forrása (automatikus, Google Táblázatokból):** három közös táblázat, mindegyik egészben, Excel (.xlsx) formátumban közzétéve: a **„Csapat adatai”** (Csapatvezetés, Rajok, Számlálók, Táborok; szűk kör szerkeszti), a **„Vezetői táblázat”** (Programok, Értesítők, Eszközök, Eszközök kapcsolattartója; minden vezető szerkeszti) és a **„Pénzügyek”** (Tagdíj, Nagytábordíj, Kcs tábordíj). Mindegyikben az első lap a Leírás. Egy GitHub-feladat (`.github/workflows/sync-sheets.yml`) óránként lefuttatja a `tools/sync_*.py` szkripteket, amelyek újraírják az oldalak megjelölt (`<!-- …:START/END -->`) részeit; hibás táblázatnál az érintett rész változatlan marad, a futás pirosan jelzi a hibát. A lapokat és a fejléc-oszlopokat nem szabad átnevezni.
- **Értesítők (piros sáv minden oldal tetején, külön Google Táblázatból):** a Vezetői táblázat "Értesítők" lapja (oszlopok: Cím · Mettől · Meddig · Határidő · Üzenet · Megjelenjen?, útmutató lappal; az eredeti a Google Drive-on van) minden sora egy üzenet, pl. tagdíj- vagy tábori jelentkezési határidő. Ugyanaz az óránkénti feladat futtatja a `tools/sync_notices.py`-t, amely mind a 13 HTML oldal `NOTICES:START/END` szakaszát újraírja. Az üzenetek alapból rejtettek; a `script.js` (`updateNotices`) mutatja azokat, amelyeknél a mai nap a Mettől és a Meddig közé esik (üres Meddig esetén a Határidő napjáig, ha az is üres, korlát nélkül). A látogató bezárhatja a sávot: az oldalon belüli lapozás alatt rejtve marad, de újratöltéskor vagy a böngészőlap újbóli megnyitásakor újra megjelenik (ugyanígy a főoldali „Közelgő programok” fül, amely a ma és a következő 7 napban kezdődő programokat mutatja). Üres táblázat megengedett: ilyenkor nincs sáv. Teszt a konzolban: `updateNotices(new Date('2026-11-16T10:00:00'))`.
- **Számlálók (Tag / Raj / Őrs kártyák, külön Google Táblázatból):** a Csapat adatai táblázat "Számlálók" lapja (oszlopok: Felirat · Szám · Megjelenjen?) minden sora egy kártya. Az óránkénti feladat a `tools/sync_counters.py`-t is futtatja, amely a főoldal "Csapatunk" szövege alatti és a Rólunk oldal "Csapatunkról" címe alatti `COUNTERS:START/END` szakaszt írja újra. A `script.js` (`initCounters`) odagörgetéskor a számjegyeket kilométeróra-szerűen feltekeri (JS nélkül és csökkentett mozgás beállításnál a végső szám áll ott).
- **Eszközbérlés (`eszkozok.html`, fejléc-menüpont, külön Google Táblázatból):** a Vezetői táblázat két lapja, az "Eszközök" (Eszköz · Darabszám · Megjegyzés · Megjelenjen?) és az "Eszközök kapcsolattartója" (Név · Szerep · E-mail · Telefon · Fájlnév · Megjelenjen?). Az óránkénti feladat a `tools/sync_equipment.py`-t futtatja, amely az `EQUIPMENT` és `EQUIPMENT_CONTACT` szakaszt írja újra. A bevezető szöveg kézzel szerkeszthető az oldalon. Ha nincs megjelenő kapcsolattartó, a 802@cserkesz.hu cím kerül a kártyára. Helyi teszt: `python3 tools/sync_equipment.py --file e.csv --contact-file k.csv`.
- **Csapatparancsnok és helyettesek (Csapatvezetés táblázat + Google Drive "Képek" mappa):** a főoldal Kapcsolat kártyáit és a Csapatotthonunk Bezsilla-kártyáját a `tools/sync_leaders.py` generálja a táblázatból (Név · Szerep · Bemutatkozás · E-mail · Telefon · Fotó · Megjelenjen?). A „Fotó” oszlopba csak a Drive-on lévő kép fájlnevét kell írni; a szkript letölti, kicsinyíti, WebP-be alakítja (`images/webp/kozos/team/<név>.webp`). Ehhez kell egy Drive API-ra korlátozott Google API-kulcs a GitHub Secrets-ben (`GOOGLE_API_KEY`); nélküle a kártyák frissülnek, a fotók nem. Részletek: AGENT_HANDOFF.md, 6. pont.
- **Lejárt események (automatikus):** az esemény napja után az esemény `Elmúlt` címkével, halványítva a lista végére kerül, majd a rács (`#newsGrid`) `data-keep-days` attribútumában megadott nap (alapból 7) után elrejtődik. Ha nincs látható hír, egy üzenet jelenik meg a Facebook/Instagram linkekkel. A `data-date` nélküli hír mindig látszik. Elrejtés csak a böngészőben történik, a HTML-ből néha érdemes kitörölni a régi blokkokat. Teszteléshez a böngésző konzoljában: `updateNews(new Date('2026-10-12T10:00:00'))`.
- **Pénzügyek oldal (egy Google Táblázatból):** három fül (Tagdíj, Nagytábordíj, Kcs tábordíj), a menüből nyitható (`penzugyek.html#tagdij`, `#nagytabor`, `#kcstabor`). A táblázat lapjai: Leírás (útmutató) · Tagdíj · Nagytábordíj · Kcs tábordíj; egy fül-lapon egymás alatt az ALAPADATOK (megjelenési időszak, cím, bevezető, kiemelt mondat, alapüzenet, ECSET- és űrlaplink, a támogatás igénylésének határideje, költségek szövegei), DÍJAK (díjkártyák + magyarázatok), RÉSZLETEK és KÖLTSÉGEK blokk. A táblázatot egészben, Excel (.xlsx) formátumban kell közzétenni a weben, a címét a workflow `FEES_SHEET_URL` sorába kell beírni. Az időszakon kívül csak az alapüzenet látszik. A banki adatok, a közlemény-figyelmeztetés és a támogatás szövege fix (a kódban). Helyi teszt: `python3 tools/sync_fees.py --file p.xlsx`.
- **Támogass minket oldal:** fent a szöveg, alatta az adó 1%-os kép (`ado1.jpg`), majd két kártya egymás mellett (egyesület adatai, banki átutalás); mobilon egymás alá kerülnek.
- **Fotók a Rólunk és Csapatotthonunk oldalon:** a fotók a `.side-photos` blokkban vannak az oldal HTML-jében (a szekció végén); a `script.js` a szöveget h3 címek mentén egyenlő hosszú részekre bontja, és mindegyik mellé 2-3 fotót tesz kollázsként, váltakozva bal és jobb oldalra (mint a Tábor oldalon); telefonon a fotók a szöveg fölött állnak. Új kép felvételekor a `.side-photos` blokkba kell betenni, a többit a script intézi (JS nélkül a fotók a szöveg alatt rácsban látszanak).
- **Személyek bemutatkozó ablaka:** a főoldali kapcsolati kártyákra (és a Csapatotthonunk, illetve az Eszközbérlés oldal kártyáira) kattintva felugrik egy ablak a képpel, a névvel, a szereppel, a bemutatkozó szöveggel, a másolható e-mail címmel és a telefonszámmal. A tartalom a táblázatokból jön (Csapatvezetés, illetve az Eszközök táblázat Kapcsolattartó lapja), nem kézzel szerkesztendő.
- **Rajparancsnokok (automatikus léptetés):** a `csatlakozom.html`-ben minden raj kártyáján `data-grade` (osztály) és `data-school-year` (a tanév kezdő éve) van; minden szeptember 1-jén a rajok eggyel feljebb lépnek, a 9. osztályba lépett raj eltűnik (a 4–8. osztály látszik). Új 4. osztályos rajhoz másolj le egy kártyát, írd át a nevet/rajparancsnokokat, és állítsd be `data-grade="4"` + az új tanév kezdő évét (előre is felvehető, addig rejtve marad). Ha az új raj még nincs felvéve, a 4. osztálynál a "Hamarosan frissítjük!" felirat látszik.
- **Facebook / Instagram:** a főoldalon (802szentkorona) és a csapatotthon oldalon (gdlcserkeszhaz / bezsilla.villa) csak linkgombok vannak, a tartalmukat az oldal nem tölti be (így nincs külső süti/adatátadás kattintás előtt). Másik oldalhoz/profilhoz cseréld le a gombok `href`-jét.

## Még placeholder (cserélendő)

- Tábor oldal (`tabor.html`): a két tábor időpontja, helyszíne és a főszervezők neve/e-mail címe (jelenleg "Hamarosan frissítjük!" és `@example.com`)

- `https://www.YOUR-DOMAIN-HERE.com` az összes HTML fájlban, a `robots.txt`-ben és a `sitemap.xml`-ben

## Publikálás GitHub Pages-re

1. Repó létrehozása, a mappa tartalmának feltöltése (git init, add, commit, push).
2. Repo **Settings → Pages**: `main` ág, gyökér mappa.
3. Saját domain esetén: **Settings → Pages → Custom domain**, és a DNS beállítása.
