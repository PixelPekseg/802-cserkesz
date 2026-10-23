#!/usr/bin/env python3
"""Updates the camp cards on tabor.html from the Táborok sheet.

Usage:
    python tools/sync_camps.py                 # from TEAM_SHEET_URL
    python tools/sync_camps.py --xlsx t.xlsx   # from a local copy of the shared workbook
    python tools/sync_camps.py --file x.csv    # from a local CSV file (for testing)

Rewrites the part of tabor.html between <!-- CAMPS:START --> and <!-- CAMPS:END -->.
On a broken sheet it stops with an error and changes nothing.
"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common

PAGE = os.path.join(common.ROOT, 'tabor.html')
SNAPSHOT = os.path.join(common.ROOT, 'data', 'camps.csv')
PLACEHOLDER = 'Hamarosan frissítjük!'

COLUMNS = {
    'name': 'név', 'lead': 'rövid leírás', 'time': 'időpont', 'place': 'helyszín',
    'n1': 'főszervező 1 neve', 'e1': 'főszervező 1 e-mail', 't1': 'főszervező 1 telefon',
    'n2': 'főszervező 2 neve', 'e2': 'főszervező 2 e-mail', 't2': 'főszervező 2 telefon',
    'n3': 'főszervező 3 neve', 'e3': 'főszervező 3 e-mail', 't3': 'főszervező 3 telefon',
    'visible': 'megjelenjen',
}


def build_card(row):
    lines = [
        '        <div class="camp-card">',
        f'          <h3>{html.escape(row["name"])}</h3>',
    ]
    if row['lead']:
        lines.append(f'          <p class="camp-card-lead">{html.escape(row["lead"])}</p>')
    lines += [
        '          <p class="bank-label">Időpont</p>',
        f'          <p class="camp-card-value">{html.escape(row["time"] or PLACEHOLDER)}</p>',
        '          <p class="bank-label">Helyszín</p>',
        f'          <p class="camp-card-value">{html.escape(row["place"] or PLACEHOLDER)}</p>',
    ]
    people = []
    for i in (1, 2, 3):
        parts = []
        if row[f'n{i}']:
            parts.append(html.escape(row[f'n{i}']))
        parts += common.contact_lines(row[f'e{i}'], row[f't{i}'])
        if parts:
            people.append('<br>\n            '.join(parts))
    if people:
        lines.append('          <p class="bank-label">Főszervezők</p>')
        for person in people:
            lines.append('          <p class="camp-card-value camp-person">')
            lines.append('            ' + person)
            lines.append('          </p>')
    lines.append('        </div>')
    return '\n'.join(lines)


def main():
    args = common.get_args()
    csv_text = common.fetch(args, 'Táborok')
    table = common.read_table(csv_text, COLUMNS, required=['name', 'visible'])

    rows = []
    for line_number, row in table:
        if common.is_hidden(row['visible']):
            continue
        if not row['name']:
            common.warn(f'{line_number}. sor: nincs megadva a tábor neve, kihagyva.')
            continue
        rows.append(row)
    if not rows and not os.environ.get('ALLOW_EMPTY'):
        common.fail('Egyetlen megjelenő tábor sincs a táblázatban, ezért nem írom felül az oldalt.')

    body = '\n\n'.join(build_card(row) for row in rows)
    changed = common.replace_block(PAGE, 'CAMPS', body, ' ' * 8)
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(rows)} tábor-kártya, tabor.html {"frissítve" if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
