#!/usr/bin/env python3
"""Updates the program cards of programok.html from the Programok sheet.

Usage:
    python tools/sync_programs.py                 # from LEADERS_SHEET_URL
    python tools/sync_programs.py --xlsx v.xlsx   # from a local copy of the shared workbook
    python tools/sync_programs.py --file x.csv    # from a local CSV file (for testing)

Rewrites the section between two comments in programok.html:
    <!-- PROGRAMS:START ... -->  ...  <!-- PROGRAMS:END -->
If the download or the validation fails (e.g. the header changed, or there is no valid row at all),
the script stops with an error and changes nothing: the page keeps its last good state.
Broken single rows are skipped with a warning ("::warning::" in GitHub Actions).
A program that has not ended yet needs a contact with a name and an e-mail address (the reminder
e-mails go there); without one it is skipped with a warning.
The images and videos of the Drive folder given in the "Képek" column (a subfolder of the Drive
"Program képek" folder) go onto the card (videos are played by the Drive player)
(program_images.py; needs GOOGLE_API_KEY, DRIVE_PROGRAMS_FOLDER_ID and Pillow – without them the
existing images stay).
"""
import argparse
import csv
import datetime as dt
import html
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
from program_images import ProgramImages  # noqa: E402  (Drive images; PIL is only needed for image processing)

ROOT = common.ROOT
PAGE = os.path.join(ROOT, 'programok.html')
SNAPSHOT = os.path.join(ROOT, 'data', 'programs.csv')

MONTHS = ['január', 'február', 'március', 'április', 'május', 'június',
          'július', 'augusztus', 'szeptember', 'október', 'november', 'december']

# We match the start of the header (lowercased), so small rewordings do not break it.
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
    # the event link (its own column; the post columns below start with "facebook-poszt" / "instagram")
    'facebook': ('facebook-esemény', 'facebook esemény', 'facebook-event'),
    'fb_post': ('facebook-poszt', 'facebook poszt', 'facebook-bejegyzés'),
    'ig_post': 'instagram',
    'report': 'beszámoló',
    'images': 'képek',
    'visible': 'megjelenjen',
}
REQUIRED = ['name', 'start_date', 'visible']
# Facebook / Instagram links typed into the sheet must point there (checked before publishing)
FACEBOOK_HOSTS = {'facebook.com', 'www.facebook.com', 'm.facebook.com', 'web.facebook.com', 'fb.me', 'fb.com'}
INSTAGRAM_HOSTS = {'instagram.com', 'www.instagram.com', 'instagr.am'}

warn, fail = common.warn, common.fail
EMAIL = common.EMAIL


def missing_contact_email(row):
    """Why the row breaks the "every contact needs an e-mail" rule, or '' if it does not.
    The reminder e-mails (photos, report) go to these addresses, so an upcoming program needs at
    least the first contact with an e-mail, and a named second contact needs one too."""
    if not row['c1_name'] and not row['c2_name']:
        return 'nincs megadva kapcsolattartó (név és e-mail cím kötelező)'
    for number in ('1', '2'):
        name, email = row[f'c{number}_name'], row[f'c{number}_email']
        if name and not email:
            return f'a(z) {number}. kapcsolattartónak ({name}) nincs megadva e-mail címe (kötelező)'
        if email and not EMAIL.fullmatch(email):
            return f'a(z) {number}. kapcsolattartó e-mail címe nem tűnik érvényesnek ("{email}")'
        if email and not name:
            return f'a(z) {number}. kapcsolattartónak nincs megadva a neve (kötelező)'
    return ''


parse_date = common.parse_date   # 2026.11.30., 2026-11-30 or 2026. november 30.


def parse_time(text):
    match = re.search(r'(\d{1,2})[:.](\d{2})', text or '')
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f'{hour:02d}:{minute:02d}'


def slugify(text):
    return common.slugify(text, 'program', limit=40)


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


def phone_link(phone):
    return common.contact_lines('', phone)[0]


def contact_html(name, email, phone):
    """One contact: name, e-mail and/or phone (all optional). Also recognises a phone number in the
    old combined "e-mail vagy telefon" column."""
    name, email, phone = name.strip(), email.strip(), phone.strip()
    if email and '@' not in email and not phone:
        email, phone = '', email
    first = [html.escape(name)] if name else []
    if email and EMAIL.fullmatch(email):
        first.append(f'<a class="inline-link" href="mailto:{html.escape(email, quote=True)}">{html.escape(email)}</a>')
    elif email:
        first.append(html.escape(email))
    text = ', '.join(first)
    if phone:   # the phone number always goes on a new line (below the name or the e-mail)
        text = (text + '<br>\n            ' if text else '') + phone_link(phone)
    return text


def card_ids(rows):
    """The cards' ids (also the link targets: programok.html#<id>, and the Google Calendar events'
    base): name-date, and -2, -3 … for programs with the same name on the same day."""
    used, ids = set(), []
    for row in rows:
        base = f"{slugify(row['name'])}-{row['start']:%Y%m%d}"
        card_id, n = base, 2
        while card_id in used:
            card_id = f'{base}-{n}'
            n += 1
        used.add(card_id)
        ids.append(card_id)
    return ids


def build_card(row, card_id):
    start, end = row['start'], row['end']

    # the last day for the page (archive, calendar): a program running past midnight (e.g. 22:00–02:00)
    # ends the next day, so its card moves to the archive only after that day
    last = end if end and end > start else start
    if last == start and row['start_time'] and row['end_time'] and row['end_time'] <= row['start_time']:
        last += dt.timedelta(days=1)
    end_attr = f' data-end-date="{last.isoformat()}"' if last > start else ''
    lines = [
        f'        <article class="news-card" id="{card_id}" data-date="{start.isoformat()}"{end_attr}>',
        f'          <div class="news-meta"><span class="news-date">{display_date(start, end)}</span></div>',
        f'          <h3>{html.escape(row["name"])}</h3>',
    ]

    # description (for upcoming programs) and report (hidden; script.js shows it instead of the
    # description once the program is in the archive). The Facebook link only goes at the end of
    # the description (.news-fb), and it is hidden in the archive too.
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

    # the program's Facebook / Instagram posts (shown in the archive too)
    posts = [f'<a class="inline-link" href="{html.escape(url, quote=True)}" target="_blank" '
             f'rel="noopener noreferrer">{label}</a>'
             for url, label in ((row.get('fb_post'), 'Facebook'), (row.get('ig_post'), 'Instagram')) if url]
    if posts:
        lines.append(f'          <p class="news-detail news-posts"><strong>Posztjaink:</strong> {" · ".join(posts)}</p>')

    if row.get('images'):
        # images at the bottom of the card (above "Üzenet másolása"): 2 visible at a time, with more
        # images arrows on both sides; clicking opens the lightbox (script.js)
        many = len(row['images']) > 2
        lines.append('          <div class="news-gallery" data-gallery>')
        if many:
            lines.append('            <button class="gallery-btn gallery-prev" type="button" aria-label="Előző képek" disabled>&#8249;</button>')
        lines.append('            <div class="news-gallery-track">')
        for n, item in enumerate(row['images'], start=1):
            # video: played by the Drive player (in the pop-up, on click); here only its preview
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
    if not any(any(c.strip() for c in row) for row in reader):
        fail('A táblázat üres.')
    header_row, index = common.find_header(reader, COLUMNS, REQUIRED)

    def cell(row, key):
        i = index.get(key)
        value = row[i].strip() if i is not None and i < len(row) else ''
        if common.is_sheet_error(value):
            warn(f'Egy cellában táblázathiba van ({value}), üresnek veszem. (Telefonszámnál a "+" jel okozza: '
                 'állítsd az oszlopot Egyszerű szövegre, vagy írd így: \'+36 …)')
            return ''
        if key != 'visible' and common.is_placeholder(value):
            common.placeholder_warning(f'Programok, "{reader[header_row][i].strip()}" oszlop', value)
            return ''
        return value

    parsed = []
    for line_number, row in enumerate(reader[header_row + 1:], start=header_row + 2):
        if not any(c.strip() for c in row):
            continue  # completely empty row
        label = f'{line_number}. sor ({cell(row, "name") or "név nélkül"})'
        if common.is_hidden(cell(row, 'visible')):
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
        if cell(row, 'end_time') and not end_time:
            warn(f'{label}: hibás befejező idő ("{cell(row, "end_time")}"), figyelmen kívül hagyva.')
        if end_time and not start_time:
            warn(f'{label}: van befejező idő, de nincs kezdő idő, a befejező idő figyelmen kívül marad.')
            end_time = None
        # an end time before the start time means the next day (e.g. a night hike 22:00–02:00);
        # only an identical start and end time is surely a typo
        if start_time and end_time and end_time == start_time:
            warn(f'{label}: a kezdő és a befejező idő ugyanaz ({start_time}), a befejező idő figyelmen kívül marad.')
            end_time = None
        facebook = cell(row, 'facebook')
        if facebook and not common.safe_url(facebook, FACEBOOK_HOSTS):
            warn(f'{label}: a Facebook-link nem https://…facebook.com/ cím, kihagyva a linket.')
            facebook = ''
        posts = {}
        for key, hosts, site in (('fb_post', FACEBOOK_HOSTS, 'Facebook'), ('ig_post', INSTAGRAM_HOSTS, 'Instagram')):
            posts[key] = cell(row, key)
            if posts[key] and not common.safe_url(posts[key], hosts):
                warn(f'{label}: {"az" if site == "Instagram" else "a"} {site}-poszt linkje nem https://…{site.lower()}.com/ cím, kihagyva a linket.')
                posts[key] = ''
        record = {
            'name': cell(row, 'name'), 'start': start, 'end': end,
            'start_time': start_time, 'end_time': end_time,
            'time_note': cell(row, 'time_note'), 'place': cell(row, 'place'),
            'description': cell(row, 'description'), 'report': cell(row, 'report'),
            'c1_name': cell(row, 'c1_name'), 'c1_email': cell(row, 'c1_email'), 'c1_phone': cell(row, 'c1_phone'),
            'c2_name': cell(row, 'c2_name'), 'c2_email': cell(row, 'c2_email'), 'c2_phone': cell(row, 'c2_phone'),
            'facebook': facebook, **posts, 'image_folder': cell(row, 'images'), 'label': label,
        }
        for number in ('1', '2'):
            record[f'c{number}_email'] = common.first_email(record[f'c{number}_email'],
                                                            f'{label}, {number}. kapcsolattartó')
        # the contact e-mail is required, but only checked for programs that have not ended yet
        # (an old row is not worth fixing; it stays on the page as before)
        upcoming = (end or start) >= dt.date.today()
        problem = missing_contact_email(record) if upcoming else ''
        if upcoming and not problem:
            missing = [what for what, key in (('helyszín', 'place'), ('leírás', 'description')) if not record[key]]
            if missing:
                warn(f'{label}: nincs megadva {" és ".join(missing)} (a program így is megjelenik, de érdemes '
                     'pótolni).')
        if problem:
            warn(f'{label}: {problem}, ezért a program nem jelenik meg. Pótold a táblázatban.')
            continue
        parsed.append(record)
    parsed.sort(key=lambda r: (r['start'], r['start_time'] or ''))
    return parsed, 'images' in index   # whether the sheet has a "Képek" column at all


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', help='local CSV export of the Programok sheet (for testing)')
    parser.add_argument('--xlsx', help='local .xlsx copy of the shared leaders workbook')
    args = parser.parse_args()

    csv_text = common.fetch(args, 'Programok', book_env=common.LEADERS_SHEET_ENV)
    rows, rows_have_image_column = parse_rows(csv_text)
    if not rows and not os.environ.get('ALLOW_EMPTY'):
        fail('Egyetlen érvényes, megjelenő program sincs a táblázatban, ezért nem írom felül az oldalt.')

    images = ProgramImages()
    for row in rows:
        row['images'] = images.images_for(row['image_folder'], row['label'])
    has_image_column = rows_have_image_column
    if not has_image_column:
        warn('A táblázatban nincs "Képek" oszlop, ezért a programképeket most nem törlöm (a meglévők maradnak).')
    images.finish(allow_delete=has_image_column)

    cards = '\n\n'.join(build_card(row, card_id) for row, card_id in zip(rows, card_ids(rows)))

    changed = common.replace_block(PAGE, 'PROGRAMS', cards, ' ' * 8)
    common.save_snapshot(SNAPSHOT, csv_text)

    print(f'{len(rows)} program; frissített képek: {len(images.updated)}; '
          f'programok.html {"frissítve" if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
