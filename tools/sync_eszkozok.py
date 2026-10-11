#!/usr/bin/env python3
"""A közzétett Google Táblázat két lapja (Eszközök, Kapcsolattartó; CSV) alapján frissíti
az eszkozok.html (Eszközbérlés) eszközlistáját és kapcsolattartó-kártyáját.

Használat:
    python tools/sync_eszkozok.py      # az ESZKOZOK_CSV_URL és ESZKOZ_KAPCSOLAT_CSV_URL változókból tölt
    python tools/sync_eszkozok.py --url <eszközök link> --contact-url <kapcsolattartó link>
    python tools/sync_eszkozok.py --file e.csv --contact-file k.csv   # helyi fájlokból (teszteléshez)

Az eszkozok.html <!-- ESZKOZOK:START/END --> és <!-- ESZKOZ_KAPCSOLAT:START/END -->
közötti részét írja újra. Ha nincs megjelenő kapcsolattartó, a csapat közös e-mail címe
kerül az oldalra. Minden kapcsolattartó a főoldalihoz hasonló személykártyát kap (person_card.py);
a fotó a Kapcsolattartó lap "Fájlnév" oszlopa alapján a Drive "Képek" mappájából jön
(drive_photos.py), ha nincs, monogram látszik.
Hibás táblázat esetén hibával leáll, és semmit nem módosít.
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
SNAPSHOTS = (os.path.join(common.ROOT, 'data', 'eszkozok.csv'),
             os.path.join(common.ROOT, 'data', 'eszkoz_kapcsolat.csv'))
FALLBACK_EMAIL = '802@cserkesz.hu'

ITEM_COLUMNS = {'name': 'eszköz', 'count': 'darabszám', 'note': 'megjegyzés', 'visible': 'megjelenjen'}
CONTACT_COLUMNS = {'name': 'név', 'role': 'szerep', 'email': 'e-mail', 'phone': 'telefon', 'filename': 'fájlnév',
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
    """Minden kapcsolattartó egy személykártya (mint a főoldalon); ha nincs, a csapat közös címe."""
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
    args = parser.parse_args()

    items_csv = common.fetch(argparse.Namespace(url=args.url, file=args.file), 'ESZKOZOK_CSV_URL')
    contacts_csv = common.fetch(argparse.Namespace(url=args.contact_url, file=args.contact_file),
                                'ESZKOZ_KAPCSOLAT_CSV_URL')

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
        row['emails'] = []
        for email in re.split(r'[,;\s]+', row['email']):
            if email and '@' in email:
                row['emails'].append(email)
            elif email:
                common.warn(f'Kapcsolattartó, {line_number}. sor: az e-mail cím nem tűnik érvényesnek, kihagyva: "{email}"')
        row['photo'] = photos.photo_for(row['name'], row['filename'], f'Kapcsolattartó, {line_number}. sor ({row["name"]})')
        contacts.append(row)

    changed = common.replace_block(PAGE, 'ESZKOZOK', build_items(items), ' ' * 8)
    changed = common.replace_block(PAGE, 'ESZKOZ_KAPCSOLAT', build_contacts(contacts), ' ' * 10) or changed
    photos.save_state()
    common.save_snapshot(SNAPSHOTS[0], items_csv)
    common.save_snapshot(SNAPSHOTS[1], contacts_csv)
    print(f'{len(items)} eszköz, {len(contacts)} kapcsolattartó; eszkozok.html {"frissítve" if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
