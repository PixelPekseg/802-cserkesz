#!/usr/bin/env python3
"""A közzétett Google Táblázat (Értesítők lap, CSV) alapján frissíti az oldal tetején
megjelenő piros értesítősávot – minden HTML oldalon.

Használat:
    python tools/sync_ertesitok.py                # az ERTESITOK_CSV_URL környezeti változóból tölt
    python tools/sync_ertesitok.py --url <link>
    python tools/sync_ertesitok.py --file x.csv   # helyi fájlból (teszteléshez)

Minden oldal <!-- ERTESITOK:START --> és <!-- ERTESITOK:END --> közötti részét írja újra.
Az értesítők alapból rejtettek; a script.js (updateNotices) a data-from / data-until
dátumok alapján mutatja őket, így a megjelenés és az eltűnés újabb szinkron nélkül is
pontos. Az üres lista megengedett (nincs értesítő = nincs sáv).
Hibás táblázat esetén hibával leáll, és semmit nem módosít.
"""
import datetime as dt
import hashlib
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common

PAGES = ['index.html', 'rolunk.html', 'tabor.html', 'csatlakozom.html', 'csapatotthon.html',
         'programok.html', 'tamogass.html', 'eszkozok.html', 'dokumentumok.html', '404.html']
SNAPSHOT = os.path.join(common.ROOT, 'data', 'ertesitok.csv')
MONTHS = ['január', 'február', 'március', 'április', 'május', 'június', 'július',
          'augusztus', 'szeptember', 'október', 'november', 'december']

COLUMNS = {
    'title': 'cím', 'from': 'mettől', 'until': 'meddig', 'deadline': 'határidő',
    'message': 'üzenet', 'visible': 'megjelenjen',
}


def parse_date(text):
    match = re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', text or '')
    if not match:
        return None
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def hungarian_date(date):
    return f'{date.year}. {MONTHS[date.month - 1]} {date.day}.'


def read_date(row, key, line_number, label):
    """A cella dátuma, vagy None; ha ki van töltve, de nem értelmezhető, figyelmeztet."""
    if not row[key]:
        return None
    date = parse_date(row[key])
    if date is None:
        common.warn(f'{line_number}. sor: a(z) "{label}" nem értelmezhető dátum ("{row[key]}"), figyelmen kívül hagyva.')
    return date


def build_notice(row, start, until, deadline):
    # Az azonosító a tartalomból készül: ha a szöveg változik, a bezárt értesítő újra megjelenik.
    key = '\n'.join([row['title'], row['message'], deadline.isoformat() if deadline else ''])
    notice_id = hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]
    attrs = [f'class="notice"', f'data-id="{notice_id}"']
    if start:
        attrs.append(f'data-from="{start.isoformat()}"')
    if until:
        attrs.append(f'data-until="{until.isoformat()}"')
    text = [f'<strong class="notice-title">{html.escape(row["title"])}</strong>']
    if deadline:
        text.append(f'<span class="notice-deadline">Határidő: {hungarian_date(deadline)}</span>')
    if row['message']:
        text.append(f'<span class="notice-message">{html.escape(row["message"])}</span>')
    return '\n'.join([
        f'    <div {" ".join(attrs)} hidden>',
        '      <div class="container notice-inner">',
        '        <p class="notice-text">',
        '          ' + '\n          '.join(text),
        '        </p>',
        '        <button type="button" class="notice-close" aria-label="Értesítés bezárása">&times;</button>',
        '      </div>',
        '    </div>',
    ])


def main():
    args, env_name = common.get_args('ERTESITOK_CSV_URL')
    csv_text = common.fetch(args, env_name)
    table = common.read_table(csv_text, COLUMNS, required=['title', 'message', 'visible'])
    today = dt.date.today()

    notices = []
    for line_number, row in table:
        if row['visible'].lower() == 'nem':
            continue
        if not row['title'] and not row['message']:
            common.warn(f'{line_number}. sor: nincs se cím, se üzenet, kihagyva.')
            continue
        start = read_date(row, 'from', line_number, 'Mettől')
        until = read_date(row, 'until', line_number, 'Meddig')
        deadline = read_date(row, 'deadline', line_number, 'Határidő')
        until = until or deadline
        if until and until < today:
            continue  # már lejárt – az oldalra sem kerül
        notices.append(build_notice(row, start, until, deadline))

    if notices:
        body = '\n'.join(['  <div class="notice-bar" id="noticeBar">', *notices, '  </div>'])
    else:
        body = '  <div class="notice-bar" id="noticeBar"></div>'

    changed = []
    for page in PAGES:
        if common.replace_block(os.path.join(common.ROOT, page), 'ERTESITOK', body, '  '):
            changed.append(page)
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(notices)} értesítő; frissített oldalak: {", ".join(changed) if changed else "nincs"}.')


if __name__ == '__main__':
    main()
