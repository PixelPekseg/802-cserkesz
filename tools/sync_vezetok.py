#!/usr/bin/env python3
"""A közzétett Google Táblázat (Csapatvezetés lap, CSV) alapján frissíti a csapatparancsnok
és a helyettesek kártyáit a főoldal "Kapcsolat" részén, valamint a Bezsilla-felelős kártyáját
a Csapatotthonunk oldalon, és a pénzügyi felelősét a Pénzügyek oldalon. Oszlopok: Név · Szerep · Bemutatkozás (rövid szöveg) · E-mail (egy) ·
Telefon · Fotó (a Drive "Képek" mappájában lévő fájl neve; drive_photos.py) · Megjelenjen?

Használat:
    python tools/sync_vezetok.py
        # VEZETOK_CSV_URL, GOOGLE_API_KEY, DRIVE_KEPEK_FOLDER_ID környezeti változókból
    python tools/sync_vezetok.py --file v.csv          # helyi CSV-ből
    DRIVE_LOCAL_DIR=./kepek python tools/sync_vezetok.py --file v.csv   # Drive helyett helyi mappa

Az index.html <!-- VEZETOK:START/END --> és a csapatotthon.html
<!-- VEZETOK_BEZSILLA:START/END --> és a penzugyek.html <!-- VEZETOK_PENZUGY:START/END --> közötti
részét írja újra. A Csapatotthonunk oldalra az kerül, akinek a szerepében szerepel a "csapatotthon"
szó, a Pénzügyek oldalra az, akinek a szerepében a "pénzügy" szó. A kártyára kattintva a script.js
felugró ablakban mutatja a rejtett .person-bio tartalmát.
Hibás táblázat esetén hibával leáll, és semmit nem módosít.
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
SNAPSHOT = os.path.join(common.ROOT, 'data', 'vezetok.csv')
# akinek a szerepében ez a szó szerepel, a Csapatotthonunk oldalra is bekerül
HOME_ROLE_WORD = 'csapatotthon'
FINANCE = os.path.join(common.ROOT, 'penzugyek.html')
# akinek a szerepében ez a szó szerepel, a Pénzügyek oldalra is bekerül
FINANCE_ROLE_WORD = 'pénzügy'

COLUMNS = {
    'name': 'név', 'role': 'szerep', 'intro': 'bemutatkozás', 'email': 'e-mail', 'phone': 'telefon',
    'filename': ('fotó', 'fájlnév'), 'visible': 'megjelenjen',
}


def main():
    args, env_name = common.get_args('VEZETOK_CSV_URL')
    csv_text = common.fetch(args, env_name)
    table = common.read_table(csv_text, COLUMNS, required=['name', 'role', 'visible'])
    photos = PhotoSync()

    people = []
    for line_number, row in table:
        if row['visible'].lower() == 'nem':
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
    changed = [p for p, ok in [('index.html', common.replace_block(INDEX, 'VEZETOK', index_body, ' ' * 8))] if ok]

    bezsilla = [row for row in people if HOME_ROLE_WORD in row['role'].lower()]
    if bezsilla:
        home_body = '\n\n'.join(build_card(row, row['photo'], ' ' * 8) for row in bezsilla)
        if common.replace_block(HOME, 'VEZETOK_BEZSILLA', home_body, ' ' * 8):
            changed.append('csapatotthon.html')
    else:
        common.warn('Senkinek a szerepében nincs "Csapatotthon", a Csapatotthonunk oldal kártyája változatlan marad.')

    finance = [row for row in people if FINANCE_ROLE_WORD in row['role'].lower()]
    if finance:
        finance_body = '\n\n'.join(build_card(row, row['photo'], ' ' * 8) for row in finance)
        if common.replace_block(FINANCE, 'VEZETOK_PENZUGY', finance_body, ' ' * 8):
            changed.append('penzugyek.html')
    else:
        common.warn('Senkinek a szerepében nincs "Pénzügy", a Pénzügyek oldal kártyája változatlan marad.')

    photos.save_state()
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(people)} vezető; frissített fotók: {", ".join(photos.updated) or "nincs"}; '
          f'frissített oldalak: {", ".join(changed) or "nincs"}.')


if __name__ == '__main__':
    main()
