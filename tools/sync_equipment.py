#!/usr/bin/env python3
"""Updates the equipment list and the contact card of eszkozok.html (Eszközbérlés) from two
sheets (Eszközök, Eszközök kapcsolattartója).

Usage:
    python tools/sync_equipment.py                 # from LEADERS_SHEET_URL (or the old
                                                   # EQUIPMENT_CSV_URL and EQUIPMENT_CONTACT_CSV_URL)
    python tools/sync_equipment.py --xlsx v.xlsx   # from a local copy of the shared workbook
    python tools/sync_equipment.py --file e.csv --contact-file k.csv   # from local CSV files (for testing)

Rewrites the parts of eszkozok.html between <!-- EQUIPMENT:START/END --> and
<!-- EQUIPMENT_CONTACT:START/END -->. Without a visible contact, the team's shared e-mail address
is used. Every contact gets a person card like on the home page (person_card.py); the photo comes
from the Drive "Képek" folder by the "Fájlnév" column (drive_photos.py), otherwise a monogram is shown.
On a broken sheet it stops with an error and changes nothing.
"""
import argparse
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common
from drive_photos import PhotoSync
from person_card import build_card

PAGE = os.path.join(common.ROOT, 'eszkozok.html')
SNAPSHOTS = (os.path.join(common.ROOT, 'data', 'equipment.csv'),
             os.path.join(common.ROOT, 'data', 'equipment_contacts.csv'))
FALLBACK_EMAIL = '802@cserkesz.hu'

ITEM_COLUMNS = {'name': 'eszköz', 'count': 'darabszám', 'note': 'megjegyzés', 'visible': 'megjelenjen'}
CONTACT_COLUMNS = {'name': 'név', 'role': 'szerep', 'email': 'e-mail', 'phone': 'telefon', 'filename': ('fotó', 'fájlnév'),
                   'visible': 'megjelenjen'}


def build_items(rows):
    lines = ['        <ul class="gear-list">']
    for row in rows:
        lines.append('          <li class="gear-item">')
        lines.append(f'            <span class="gear-name">{html.escape(row["name"])}</span>')
        if row['note']:
            lines.append(f'            <span class="gear-note">{html.escape(row["note"])}</span>')
        if row['count']:
            lines.append(f'            <span class="gear-count">{row["count"]} db</span>')
        lines.append('          </li>')
    lines.append('        </ul>')
    return '\n'.join(lines)


def build_contacts(rows):
    """Every contact is a person card (as on the home page); without one, the team's shared address."""
    if not rows:
        common.warn('Nincs megjelenő kapcsolattartó, a csapat közös e-mail címe kerül az oldalra.')
        safe = html.escape(FALLBACK_EMAIL, quote=True)
        return f'          <p class="bank-value"><a class="inline-link" href="mailto:{safe}">{safe}</a></p>'
    cards = '\n\n'.join(build_card(row, row['photo'], ' ' * 12) for row in rows)
    return '          <div class="gear-contact-cards">\n' + cards + '\n          </div>'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url')
    parser.add_argument('--file')
    parser.add_argument('--contact-url')
    parser.add_argument('--contact-file')
    parser.add_argument('--xlsx', help='local .xlsx copy of the shared leaders workbook')
    args = parser.parse_args()

    items_csv = common.fetch(argparse.Namespace(url=args.url, file=args.file, xlsx=args.xlsx), 'EQUIPMENT_CSV_URL',
                             sheet='Eszközök', book_env=common.LEADERS_SHEET_ENV)
    contacts_csv = common.fetch(argparse.Namespace(url=args.contact_url, file=args.contact_file, xlsx=args.xlsx),
                                'EQUIPMENT_CONTACT_CSV_URL', sheet='Eszközök kapcsolattartója', book_env=common.LEADERS_SHEET_ENV)

    items = []
    for line_number, row in common.read_table(items_csv, ITEM_COLUMNS, required=['name', 'visible']):
        if row['visible'].lower() == 'nem':
            continue
        if not row['name']:
            common.warn(f'Eszközök, {line_number}. sor: nincs megadva az eszköz neve, kihagyva.')
            continue
        count = row.get('count', '').replace(' ', '')
        if count and not count.isdigit():
            common.warn(f'Eszközök, {line_number}. sor: a darabszám nem egész szám ("{row["count"]}"), elhagyva.')
            count = ''
        row['count'] = count
        row.setdefault('note', '')
        items.append(row)
    if not items:
        common.fail('Egyetlen megjelenő eszköz sincs a táblázatban, ezért nem írom felül az oldalt.')

    photos = PhotoSync()
    contacts = []
    for line_number, row in common.read_table(contacts_csv, CONTACT_COLUMNS, required=['name', 'visible']):
        if row['visible'].lower() == 'nem':
            continue
        if not row['name']:
            common.warn(f'Kapcsolattartó, {line_number}. sor: nincs megadva a név, kihagyva.')
            continue
        for key in ('role', 'email', 'phone', 'filename'):
            row.setdefault(key, '')
        row['role'] = row['role'] or 'Kapcsolattartó'
        emails = [e for e in re.split(r'[,;\s]+', row['email']) if e]
        row['email'] = emails[0] if emails and '@' in emails[0] else ''
        if emails and not row['email']:
            common.warn(f'Kapcsolattartó, {line_number}. sor: az e-mail cím nem tűnik érvényesnek, kihagyva: "{emails[0]}"')
        row['photo'] = photos.photo_for(row['name'], row['filename'], f'Kapcsolattartó, {line_number}. sor ({row["name"]})')
        contacts.append(row)

    changed = common.replace_block(PAGE, 'EQUIPMENT', build_items(items), ' ' * 8)
    changed = common.replace_block(PAGE, 'EQUIPMENT_CONTACT', build_contacts(contacts), ' ' * 10) or changed
    photos.save_state()
    common.save_snapshot(SNAPSHOTS[0], items_csv)
    common.save_snapshot(SNAPSHOTS[1], contacts_csv)
    print(f'{len(items)} eszköz, {len(contacts)} kapcsolattartó; eszkozok.html {"frissítve" if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
