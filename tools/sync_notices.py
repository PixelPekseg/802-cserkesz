#!/usr/bin/env python3
"""Updates the red notice bar at the top of every HTML page from the Értesítők sheet.

Usage:
    python tools/sync_notices.py                 # from LEADERS_SHEET_URL (or the old NOTICES_CSV_URL)
    python tools/sync_notices.py --xlsx v.xlsx   # from a local copy of the shared workbook
    python tools/sync_notices.py --file x.csv    # from a local CSV file (for testing)

Rewrites the part of every page between <!-- NOTICES:START --> and <!-- NOTICES:END -->.
Notices are hidden by default; script.js (updateNotices) shows them by their data-from /
data-until dates, so they appear and disappear on time without another sync. An empty list is
allowed (no notice = no bar).
On a broken sheet it stops with an error and changes nothing.
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
         'programok.html', 'naptar.html', 'tamogass.html', 'eszkozok.html', 'penzugyek.html', 'dokumentumok.html', 'galeria.html', '404.html']
SNAPSHOT = os.path.join(common.ROOT, 'data', 'notices.csv')
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
    """The cell's date, or None; warns if the cell is filled in but cannot be parsed."""
    if not row[key]:
        return None
    date = parse_date(row[key])
    if date is None:
        common.warn(f'{line_number}. sor: a(z) "{label}" nem értelmezhető dátum ("{row[key]}"), figyelmen kívül hagyva.')
    return date


def build_notice(row, start, until, deadline):
    # The id is derived from the content: if the text changes, a dismissed notice shows up again.
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
    args, env_name = common.get_args('NOTICES_CSV_URL')
    csv_text = common.fetch(args, env_name, sheet='Értesítők', book_env=common.LEADERS_SHEET_ENV)
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
            continue  # already expired – not even written to the page
        notices.append(build_notice(row, start, until, deadline))

    if notices:
        body = '\n'.join(['  <div class="notice-bar" id="noticeBar">', *notices, '  </div>'])
    else:
        body = '  <div class="notice-bar" id="noticeBar"></div>'

    changed = []
    for page in PAGES:
        if common.replace_block(os.path.join(common.ROOT, page), 'NOTICES', body, '  '):
            changed.append(page)
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(notices)} értesítő; frissített oldalak: {", ".join(changed) if changed else "nincs"}.')


if __name__ == '__main__':
    main()
