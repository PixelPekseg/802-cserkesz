#!/usr/bin/env python3
"""Updates the leader cards (team leader and deputies) in the "Kapcsolat" section of the home
page from the Csapatvezetés sheet, plus the house manager's card on the Csapatotthonunk page and
the finance deputy's card on the Pénzügyek page. Columns: Név · Szerep · Bemutatkozás (short
text) · E-mail (one) · Telefon · Fotó (file name in the Drive "Képek" folder; drive_photos.py) ·
Megjelenjen?

Usage:
    python tools/sync_leaders.py
        # from TEAM_SHEET_URL, GOOGLE_API_KEY, DRIVE_IMAGES_FOLDER_ID
    python tools/sync_leaders.py --xlsx t.xlsx      # from a local copy of the shared workbook
    python tools/sync_leaders.py --file v.csv       # from a local CSV file
    DRIVE_LOCAL_DIR=./kepek python tools/sync_leaders.py --file v.csv   # local folder instead of Drive

Rewrites index.html <!-- LEADERS:START/END -->, csapatotthon.html <!-- LEADERS_HOME:START/END -->
and penzugyek.html <!-- LEADERS_FINANCE:START/END -->. The Csapatotthonunk page gets whoever has the
word "csapatotthon" in their role, the Pénzügyek page whoever has "pénzügy". Clicking a card makes
script.js show the hidden .person-bio content in a pop-up.
On a broken sheet it stops with an error and changes nothing.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common
from drive_photos import PhotoSync
from person_card import build_card

INDEX = os.path.join(common.ROOT, 'index.html')
HOME = os.path.join(common.ROOT, 'csapatotthon.html')
SNAPSHOT = os.path.join(common.ROOT, 'data', 'leaders.csv')
# whoever has this word in their role also appears on the Csapatotthonunk page
HOME_ROLE_WORD = 'csapatotthon'
FINANCE = os.path.join(common.ROOT, 'penzugyek.html')
# whoever has this word in their role also appears on the Pénzügyek page
FINANCE_ROLE_WORD = 'pénzügy'

COLUMNS = {
    'name': 'név', 'role': 'szerep', 'intro': 'bemutatkozás', 'email': 'e-mail', 'phone': 'telefon',
    'filename': ('fotó', 'fájlnév'), 'visible': 'megjelenjen',
}


def main():
    args = common.get_args()
    csv_text = common.fetch(args, 'Csapatvezetés')
    table = common.read_table(csv_text, COLUMNS, required=['name', 'role', 'visible'])
    photos = PhotoSync()

    people = []
    for line_number, row in table:
        if common.is_hidden(row['visible']):
            continue
        if not row['name'] or not row['role']:
            common.warn(f'{line_number}. sor: hiányzik a név vagy a szerep, kihagyva.')
            continue
        for key in COLUMNS:
            row.setdefault(key, '')
        emails = [e for e in re.split(r'[,;\s]+', row['email']) if e]
        if len(emails) > 1:
            common.warn(f'{line_number}. sor: több e-mail cím van megadva, csak az elsőt használom.')
        row['email'] = emails[0] if emails else ''
        if row['email'] and '@' not in row['email']:
            common.warn(f'{line_number}. sor: az e-mail cím nem tűnik érvényesnek, kihagyva: "{row["email"]}"')
            row['email'] = ''
        row['photo'] = photos.photo_for(row['name'], row['filename'], f'{line_number}. sor ({row["name"]})')
        people.append(row)
    if not people:
        common.fail('Egyetlen megjelenő vezető sincs a táblázatban, ezért nem írom felül az oldalt.')

    index_body = '\n\n'.join(build_card(row, row['photo'], ' ' * 8) for row in people)
    changed = [p for p, ok in [('index.html', common.replace_block(INDEX, 'LEADERS', index_body, ' ' * 8))] if ok]

    bezsilla = [row for row in people if HOME_ROLE_WORD in row['role'].lower()]
    if bezsilla:
        home_body = '\n\n'.join(build_card(row, row['photo'], ' ' * 8) for row in bezsilla)
        if common.replace_block(HOME, 'LEADERS_HOME', home_body, ' ' * 8):
            changed.append('csapatotthon.html')
    else:
        common.warn('Senkinek a szerepében nincs "Csapatotthon", a Csapatotthonunk oldal kártyája változatlan marad.')

    finance = [row for row in people if FINANCE_ROLE_WORD in row['role'].lower()]
    if finance:
        finance_body = '\n\n'.join(build_card(row, row['photo'], ' ' * 8) for row in finance)
        if common.replace_block(FINANCE, 'LEADERS_FINANCE', finance_body, ' ' * 8):
            changed.append('penzugyek.html')
    else:
        common.warn('Senkinek a szerepében nincs "Pénzügy", a Pénzügyek oldal kártyája változatlan marad.')

    photos.save_state()
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(people)} vezető; frissített fotók: {", ".join(photos.updated) or "nincs"}; '
          f'frissített oldalak: {", ".join(changed) or "nincs"}.')


if __name__ == '__main__':
    main()
