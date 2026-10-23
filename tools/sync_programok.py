#!/usr/bin/env python3
"""A közzétett Google Táblázat (CSV) alapján frissíti a programok.html programkártyáit.

Használat:
    python tools/sync_programok.py                 # a PROGRAMOK_CSV_URL környezeti változóból tölt
    python tools/sync_programok.py --url <link>    # megadott CSV-hivatkozásból
    python tools/sync_programok.py --file x.csv    # helyi CSV-fájlból (teszteléshez)

A script a programok.html és a naptar.html (ott rejtve, a naptárnézethez) két megjegyzés közötti
szakaszát írja újra:
    <!-- PROGRAMOK:START ... -->  ...  <!-- PROGRAMOK:END -->
Ha a letöltés vagy az ellenőrzés hibás (pl. változott a fejléc, vagy egyetlen érvényes sor
sincs), a script hibával leáll, és semmit nem módosít: az oldal az utolsó jó állapotot mutatja.
Hibás egyedi sorokat kihagy, és figyelmeztetést ír (GitHub Actionsben "::warning::" jelzést).
A "Képek" oszlopban megadott Drive-mappa (Képek és videók/Program képek/<mappa>) képei és videói
a kártyára kerülnek (a videókat a Drive lejátszója játssza le)
(program_images.py; ehhez GOOGLE_API_KEY, DRIVE_KEPEK_FOLDER_ID és Pillow kell – nélkülük a meglévő
képek maradnak).
"""
import argparse
import csv
import datetime as dt
import html
import io
import os
import re
import sys
import unicodedata
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from program_images import ProgramImages  # noqa: E402  (a Drive-os képek; PIL csak képfeldolgozáskor kell)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, 'programok.html')
PAGES = [PAGE, os.path.join(ROOT, 'naptar.html')]   # a naptár oldal rejtve, a naptárnézethez
SNAPSHOT = os.path.join(ROOT, 'data', 'programok.csv')

MONTHS = ['január', 'február', 'március', 'április', 'május', 'június',
          'július', 'augusztus', 'szeptember', 'október', 'november', 'december']

# A fejléc elejét keressük (kisbetűsen), így apróbb átfogalmazás nem töri el.
COLUMNS = {
    'name': 'név',
    'start_date': 'kezdő dátum',
    'end_date': 'befejező dátum',
    'start_time': 'kezdő idő',
    'end_time': 'befejező idő',
    'time_note': 'időpont megjegyz',
    'place': 'helyszín',
    'description': 'leírás',
    'c1_name': 'kapcsolattartó 1 neve',
    'c1_email': 'kapcsolattartó 1 e-mail',
    'c1_phone': 'kapcsolattartó 1 telefon',
    'c2_name': 'kapcsolattartó 2 neve',
    'c2_email': 'kapcsolattartó 2 e-mail',
    'c2_phone': 'kapcsolattartó 2 telefon',
    'facebook': 'facebook',
    'report': 'beszámoló',
    'images': 'képek',
    'visible': 'megjelenjen',
}
REQUIRED = ['name', 'start_date', 'visible']

in_actions = os.environ.get('GITHUB_ACTIONS') == 'true'


def warn(message):
    print(('::warning::' if in_actions else 'FIGYELEM: ') + message)


def fail(message):
    print(('::error::' if in_actions else 'HIBA: ') + message)
    sys.exit(1)


def fetch(args):
    # a közös "Vezetői táblázat" Programok lapja (--xlsx vagy VEZETOI_TABLAZAT_URL), ha meg van adva
    if not args.file and (args.xlsx or os.environ.get('VEZETOI_TABLAZAT_URL')):
        import sync_common
        return sync_common.shared_sheet_csv(args, 'Programok', sync_common.VEZETOI_ENV)
    if args.file:
        with open(args.file, encoding='utf-8-sig') as handle:
            return handle.read()
    url = args.url or os.environ.get('PROGRAMOK_CSV_URL')
    if not url:
        fail('Nincs megadva a CSV címe (PROGRAMOK_CSV_URL vagy --url).')
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode('utf-8-sig')
    except Exception as error:  # hálózati hiba, 4xx/5xx stb.
        fail(f'A táblázat letöltése nem sikerült: {error}')


def resolve_columns(header):
    lowered = [cell.strip().lower() for cell in header]
    index = {}
    for key, prefix in COLUMNS.items():
        for i, cell in enumerate(lowered):
            if cell.startswith(prefix):
                index[key] = i
                break
    missing = [COLUMNS[key] for key in REQUIRED if key not in index]
    if missing:
        fail('A táblázat fejlécéből hiányzik: ' + ', '.join(missing) + '. Valaki átírta az első sort?')
    return index


def parse_date(text):
    match = re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', text or '')
    if not match:
        return None
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def parse_time(text):
    match = re.search(r'(\d{1,2})[:.](\d{2})', text or '')
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f'{hour:02d}:{minute:02d}'


def slugify(text):
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_text.lower()).strip('-')
    return slug[:40].strip('-') or 'program'


def display_date(start, end):
    def full(d):
        return f'{d.year}. {MONTHS[d.month - 1]} {d.day}.'
    if not end or end <= start:
        return full(start)
    if (start.year, start.month) == (end.year, end.month):
        return f'{start.year}. {MONTHS[start.month - 1]} {start.day}–{end.day}.'
    if start.year == end.year:
        return f'{start.year}. {MONTHS[start.month - 1]} {start.day}. – {MONTHS[end.month - 1]} {end.day}.'
    return f'{full(start)} – {full(end)}'


def fix_phone(phone):
    """Ha a táblázat a "+36 …" számot számmá alakította (pl. 36707582659), visszaadja olvasható
    formában (+36 70 758 2659). Minden más beírást változatlanul hagy. (Ld. sync_common.fix_phone.)"""
    raw = phone.strip()
    if re.fullmatch(r'36\d{9}', raw):
        return f'+36 {raw[2:4]} {raw[4:7]} {raw[7:]}'
    if re.fullmatch(r'361\d{7}', raw):
        return f'+36 1 {raw[3:6]} {raw[6:]}'
    return phone


# a Google Táblázat hibaértékei (pl. "+36 …" képletként értelmezve #ERROR! lesz) – ne kerüljenek ki az oldalra
SHEET_ERRORS = ('#ERROR!', '#NAME?', '#REF!', '#VALUE!', '#N/A', '#DIV/0!', '#NUM!', '#NULL!')


def phone_link(phone):
    phone = fix_phone(phone)
    digits = re.sub(r'[^\d+]', '', phone)
    if len(re.sub(r'\D', '', digits)) >= 6:
        return f'<a class="inline-link" href="tel:{digits}">{html.escape(phone)}</a>'
    return html.escape(phone)


def contact_html(name, email, phone):
    """Egy kapcsolattartó: név, e-mail és/vagy telefon (mind opcionális). A régi, közös
    "e-mail vagy telefon" oszlopból jövő telefonszámot is felismeri."""
    name, email, phone = name.strip(), email.strip(), phone.strip()
    if email and '@' not in email and not phone:
        email, phone = '', email
    first = [html.escape(name)] if name else []
    if email:
        first.append(f'<a class="inline-link" href="mailto:{html.escape(email, quote=True)}">{html.escape(email)}</a>')
    text = ', '.join(first)
    if phone:   # a telefonszám mindig új sorba kerül (a név, illetve az e-mail alá)
        text = (text + '<br>\n            ' if text else '') + phone_link(phone)
    return text


def build_card(row, used_ids):
    start, end = row['start'], row['end']
    base = f"{slugify(row['name'])}-{start:%Y%m%d}"
    card_id, n = base, 2
    while card_id in used_ids:
        card_id = f'{base}-{n}'
        n += 1
    used_ids.add(card_id)

    end_attr = f' data-end-date="{end.isoformat()}"' if end and end > start else ''
    lines = [
        f'        <article class="news-card" id="{card_id}" data-date="{start.isoformat()}"{end_attr}>',
        f'          <div class="news-meta"><span class="news-date">{display_date(start, end)}</span></div>',
        f'          <h3>{html.escape(row["name"])}</h3>',
    ]

    # leírás (a közelgő programoknál) és beszámoló (rejtve; a script.js mutatja a leírás helyett,
    # ha a program már az archívumba került). A Facebook-link csak a leírás végére kerül
    # (.news-fb), és az archívumban az is elrejtődik.
    def text_block(source, css_class, hidden=False, facebook=''):
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', source.strip()) if p.strip()]
        if not paragraphs and facebook:
            paragraphs = ['']
        if not paragraphs:
            return []
        block = [f'          <div class="news-text {css_class}"{" hidden" if hidden else ""}>']
        for i, paragraph in enumerate(paragraphs):
            text = html.escape(paragraph).replace('\n', '<br>')
            if facebook and i == len(paragraphs) - 1:
                link = (f'<a class="inline-link" href="{html.escape(facebook, quote=True)}" '
                        f'target="_blank" rel="noopener noreferrer">Facebook-eseményen</a>')
                text = (text + ' ' if text else '') + f'<span class="news-fb">Részletek a {link}.</span>'
            block.append(f'            <p>{text}</p>')
        block.append('          </div>')
        return block

    lines += text_block(row['description'], 'news-desc', facebook=row['facebook'])
    if row['report'].strip():
        lines += text_block(row['report'], 'news-report', hidden=True)

    if row['place']:
        lines.append(f'          <p class="news-detail"><strong>Helyszín:</strong> {html.escape(row["place"])}</p>')

    time_text = ''
    if row['start_time']:
        time_text = row['start_time'] + (f'–{row["end_time"]}' if row['end_time'] else '')
        if row['time_note']:
            time_text += f' ({row["time_note"]})'
    if time_text:
        lines.append(f'          <p class="news-detail"><strong>Időpont:</strong> {html.escape(time_text)}</p>')

    contacts = [c for c in (contact_html(row['c1_name'], row['c1_email'], row['c1_phone']),
                            contact_html(row['c2_name'], row['c2_email'], row['c2_phone'])) if c]
    if contacts:
        lines.append('          <p class="news-detail news-contact">')
        lines.append('            <strong>Kérdés esetén keresd:</strong><br>')
        lines.append('            ' + '<br>\n            '.join(contacts))
        lines.append('          </p>')

    if row.get('images'):
        # képek a kártya alján (az "Üzenet másolása" fölött): egyszerre 2 látszik, több kép esetén
        # két oldalt nyilakkal lapozható; kattintásra a nagyító nyílik (script.js)
        many = len(row['images']) > 2
        lines.append('          <div class="news-gallery" data-gallery>')
        if many:
            lines.append('            <button class="gallery-btn gallery-prev" type="button" aria-label="Előző képek" disabled>&#8249;</button>')
        lines.append('            <div class="news-gallery-track">')
        for n, item in enumerate(row['images'], start=1):
            # videó: a Drive lejátszója játssza le (a felugró ablakban, kattintásra); itt az előnézete
            video = f' data-video="{html.escape(item["video"], quote=True)}"' if item['video'] else ''
            kind = 'videó' if item['video'] else 'kép'
            alt = html.escape(f'{row["name"]} – {n}. {kind}', quote=True)
            lines.append(f'              <img src="{item["thumb"]}" data-full="{item["full"]}"{video} alt="{alt}" loading="lazy">')
        lines.append('            </div>')
        if many:
            lines.append('            <button class="gallery-btn gallery-next" type="button" aria-label="Következő képek">&#8250;</button>')
        lines.append('          </div>')

    lines.append('        </article>')
    return '\n'.join(lines)


def parse_rows(csv_text):
    reader = list(csv.reader(io.StringIO(csv_text)))
    if not reader:
        fail('A táblázat üres.')
    index = resolve_columns(reader[0])

    def cell(row, key):
        i = index.get(key)
        value = row[i].strip() if i is not None and i < len(row) else ''
        if value.upper() in SHEET_ERRORS:
            warn(f'Egy cellában táblázathiba van ({value}), üresnek veszem. (Telefonszámnál a "+" jel okozza: '
                 'állítsd az oszlopot Egyszerű szövegre, vagy írd így: \'+36 …)')
            return ''
        return value

    parsed = []
    for line_number, row in enumerate(reader[1:], start=2):
        if not any(c.strip() for c in row):
            continue  # teljesen üres sor
        label = f'{line_number}. sor ({cell(row, "name") or "név nélkül"})'
        if cell(row, 'visible').lower() == 'nem':
            continue
        if not cell(row, 'name'):
            warn(f'{label}: nincs megadva a program neve, kihagyva.')
            continue
        start = parse_date(cell(row, 'start_date'))
        if not start:
            warn(f'{label}: hibás vagy hiányzó kezdő dátum ("{cell(row, "start_date")}"), kihagyva.')
            continue
        end = parse_date(cell(row, 'end_date'))
        if cell(row, 'end_date') and (not end or end < start):
            warn(f'{label}: a befejező dátum hibás vagy a kezdő előtt van, figyelmen kívül hagyva.')
            end = None
        start_time = parse_time(cell(row, 'start_time'))
        end_time = parse_time(cell(row, 'end_time'))
        if cell(row, 'start_time') and not start_time:
            warn(f'{label}: hibás kezdő idő ("{cell(row, "start_time")}"), a program egész naposként jelenik meg.')
        if end_time and not start_time:
            warn(f'{label}: van befejező idő, de nincs kezdő idő, a befejező idő figyelmen kívül marad.')
            end_time = None
        facebook = cell(row, 'facebook')
        if facebook and not re.match(r'https?://', facebook):
            warn(f'{label}: a Facebook-link nem http(s)-sel kezdődik, kihagyva a linket.')
            facebook = ''
        parsed.append({
            'name': cell(row, 'name'), 'start': start, 'end': end,
            'start_time': start_time, 'end_time': end_time,
            'time_note': cell(row, 'time_note'), 'place': cell(row, 'place'),
            'description': cell(row, 'description'), 'report': cell(row, 'report'),
            'c1_name': cell(row, 'c1_name'), 'c1_email': cell(row, 'c1_email'), 'c1_phone': cell(row, 'c1_phone'),
            'c2_name': cell(row, 'c2_name'), 'c2_email': cell(row, 'c2_email'), 'c2_phone': cell(row, 'c2_phone'),
            'facebook': facebook, 'image_folder': cell(row, 'images'), 'label': label,
        })
    parsed.sort(key=lambda r: (r['start'], r['start_time'] or ''))
    return parsed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url')
    parser.add_argument('--file')
    parser.add_argument('--xlsx', help='a közös Vezetői táblázat helyi .xlsx fájlja')
    args = parser.parse_args()

    csv_text = fetch(args).replace('\r\n', '\n').replace('\r', '\n')
    rows = parse_rows(csv_text)
    if not rows and not os.environ.get('ALLOW_EMPTY'):
        fail('Egyetlen érvényes, megjelenő program sincs a táblázatban, ezért nem írom felül az oldalt.')

    images = ProgramImages()
    for row in rows:
        row['images'] = images.images_for(row['image_folder'], row['label'])
    images.finish()

    used_ids = set()
    cards = '\n\n'.join(build_card(row, used_ids) for row in rows)

    # ugyanazok a kártyák a Programok oldalra és (rejtve, a naptárhoz) a Naptár oldalra
    pattern = re.compile(r'(<!-- PROGRAMOK:START[^\n]*-->\n)(.*?)(\n[ \t]*<!-- PROGRAMOK:END -->)', re.S)
    changed = False
    for path in PAGES:
        with open(path, encoding='utf-8') as handle:
            page = handle.read()
        if not pattern.search(page):
            fail(f'A {os.path.basename(path)}-ben nem találom a PROGRAMOK:START / PROGRAMOK:END jelölőket.')
        new_page = pattern.sub(lambda m: m.group(1) + cards + '\n\n        <!-- PROGRAMOK:END -->', page, count=1)
        if new_page != page:
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(new_page)
            changed = True

    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    old_snapshot = open(SNAPSHOT, encoding='utf-8').read() if os.path.exists(SNAPSHOT) else None
    if old_snapshot != csv_text:
        with open(SNAPSHOT, 'w', encoding='utf-8') as handle:
            handle.write(csv_text)

    print(f'{len(rows)} program; frissített képek: {len(images.updated)}; '
          f'programok.html/naptar.html {"frissítve" if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
