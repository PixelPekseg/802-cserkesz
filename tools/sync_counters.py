#!/usr/bin/env python3
"""Updates the counter cards (members, troops, patrols …) in the "Csapatunk" section of the home
page and on the Rólunk page from the Számlálók sheet.

Usage:
    python tools/sync_counters.py                 # from TEAM_SHEET_URL
    python tools/sync_counters.py --xlsx t.xlsx   # from a local copy of the shared workbook
    python tools/sync_counters.py --file x.csv    # from a local CSV file (for testing)

Rewrites the part of the pages between <!-- COUNTERS:START --> and <!-- COUNTERS:END -->.
The card holds the final number (correct without JS too); the rolling animation comes from
script.js (initCounters) based on the data-count attribute.
On a broken sheet it stops with an error and changes nothing.
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common

# page -> indentation of the block
PAGES = {'index.html': ' ' * 8, 'rolunk.html': ' ' * 8}
SNAPSHOT = os.path.join(common.ROOT, 'data', 'counters.csv')

COLUMNS = {'label': 'felirat', 'number': 'szám', 'visible': 'megjelenjen'}


def format_number(number):
    """Hungarian thousands grouping with a non-breaking space: 1200 -> 1&nbsp;200."""
    return f'{number:,}'.replace(',', '&nbsp;')


def build_block(cards, indent):
    lines = [f'{indent}<div class="stats">']
    for label, number in cards:
        lines += [
            f'{indent}  <div class="stat-card">',
            f'{indent}    <span class="stat-number" data-count="{number}">{format_number(number)}</span>',
            f'{indent}    <span class="stat-label">{html.escape(label)}</span>',
            f'{indent}  </div>',
        ]
    lines.append(f'{indent}</div>')
    return '\n'.join(lines)


def main():
    args = common.get_args()
    csv_text = common.fetch(args, 'Számlálók')
    table = common.read_table(csv_text, COLUMNS, required=['label', 'number', 'visible'])

    cards = []
    for line_number, row in table:
        if common.is_hidden(row['visible']):
            continue
        if not row['label']:
            common.warn(f'{line_number}. sor: nincs megadva a felirat, kihagyva.')
            continue
        raw = row['number'].strip()
        # plain digits, or groups of three separated by space/dot/comma ("1 200", "1.200");
        # "4.5" or "411 fő" is rejected instead of silently becoming 45
        grouped = re.fullmatch(r'\d+|\d{1,3}(?:[\s.,\u00a0]\d{3})+', raw)
        digits = re.sub(r'\D', '', raw) if grouped else ''
        if not digits.isdigit():
            common.warn(f'{line_number}. sor: a szám nem értelmezhető ("{row["number"]}"), kihagyva.')
            continue
        cards.append((row['label'], int(digits)))
    if not cards:
        common.fail('Egyetlen megjelenő számláló sincs a táblázatban, ezért nem írom felül az oldalakat.')

    changed = []
    for page, indent in PAGES.items():
        if common.replace_block(os.path.join(common.ROOT, page), 'COUNTERS', build_block(cards, indent), indent):
            changed.append(page)
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(cards)} számláló; frissített oldalak: {", ".join(changed) if changed else "nincs"}.')


if __name__ == '__main__':
    main()
