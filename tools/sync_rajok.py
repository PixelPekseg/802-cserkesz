#!/usr/bin/env python3
"""A közzétett Google Táblázat (Rajok lap, CSV) alapján frissíti a csatlakozom.html raj-kártyáit.

Használat:
    python tools/sync_rajok.py                  # a RAJOK_CSV_URL környezeti változóból tölt
    python tools/sync_rajok.py --url <link>
    python tools/sync_rajok.py --file x.csv     # helyi fájlból (teszteléshez)

A csatlakozom.html <!-- RAJOK:START --> és <!-- RAJOK:END --> közötti részét írja újra.
Minden kártya data-grade="4" és data-school-year="<indulás éve>" attribútumot kap; az osztályt
(4. osztály = az indulás éve tanévében) a script.js számolja ki a megnyitáskor, így a szeptember
1-jei léptetés a táblázat változása nélkül is megtörténik.
"""
import datetime as dt
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common

PAGE = os.path.join(common.ROOT, 'csatlakozom.html')
SNAPSHOT = os.path.join(common.ROOT, 'data', 'rajok.csv')

COLUMNS = {
    'name': 'raj neve', 'year': 'indulás éve',
    'n1': 'rajparancsnok 1 neve', 'e1': 'rajparancsnok 1 e-mail', 't1': 'rajparancsnok 1 telefon',
    'n2': 'rajparancsnok 2 neve', 'e2': 'rajparancsnok 2 e-mail', 't2': 'rajparancsnok 2 telefon',
    'n3': 'rajparancsnok 3 neve', 'e3': 'rajparancsnok 3 e-mail', 't3': 'rajparancsnok 3 telefon',
    'visible': 'megjelenjen',
}


def school_year(today):
    return today.year if today.month >= 9 else today.year - 1


def build_card(row, start_year, today):
    grade = 4 + school_year(today) - start_year
    visible = 4 <= grade <= 8
    hidden = '' if visible else ' hidden'
    lines = [
        f'        <div class="grade-card" data-grade="4" data-school-year="{start_year}"{hidden}>',
        f'          <h3>{grade}. osztály</h3>',
        f'          <p class="grade-squad">{html.escape(row["name"])}</p>',
    ]
    items = []
    for i in (1, 2, 3):
        parts = []
        if row[f'n{i}']:
            parts.append(f'<span class="leader-name">{html.escape(row[f"n{i}"])}</span>')
        for link in common.contact_lines(row[f'e{i}'], row[f't{i}']):
            parts.append(f'<div class="leader-line">{link.replace("inline-link", "leader-email")}</div>')
        if parts:
            items.append(parts)
    if items:
        lines.append('          <ul>')
        for parts in items:
            lines.append('            <li>')
            lines += ['              ' + part for part in parts]
            lines.append('            </li>')
        lines.append('          </ul>')
    lines.append('        </div>')
    return '\n'.join(lines)


def main():
    args, env_name = common.get_args('RAJOK_CSV_URL')
    csv_text = common.fetch(args, env_name)
    table = common.read_table(csv_text, COLUMNS, required=['name', 'year', 'visible'])
    today = dt.date.today()

    cards = []
    for line_number, row in table:
        if row['visible'].lower() == 'nem':
            continue
        if not row['name']:
            common.warn(f'{line_number}. sor: nincs megadva a raj neve, kihagyva.')
            continue
        match = re.search(r'\d{4}', row['year'])
        if not match or not 2000 <= int(match.group()) <= 2100:
            common.warn(f'{line_number}. sor ({row["name"]}): hibás indulási év ("{row["year"]}"), kihagyva.')
            continue
        cards.append((int(match.group()), build_card(row, int(match.group()), today)))
    if not cards and not os.environ.get('ALLOW_EMPTY'):
        common.fail('Egyetlen érvényes, megjelenő raj sincs a táblázatban, ezért nem írom felül az oldalt.')

    cards.sort(key=lambda item: -item[0])  # a legfiatalabb (legalacsonyabb osztály) elöl
    body = '\n\n'.join(card for _, card in cards)
    changed = common.replace_block(PAGE, 'RAJOK', body, ' ' * 8)
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(cards)} raj, csatlakozom.html {"frissítve" if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
