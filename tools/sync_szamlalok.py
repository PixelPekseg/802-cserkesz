#!/usr/bin/env python3
"""A közzétett Google Táblázat (Számlálók lap, CSV) alapján frissíti a számláló-kártyákat
(Tagok, Rajok, Őrsök …) a főoldal "Csapatunk" szekciójában és a Rólunk oldalon.

Használat:
    python tools/sync_szamlalok.py                # a SZAMLALOK_CSV_URL környezeti változóból tölt
    python tools/sync_szamlalok.py --url <link>
    python tools/sync_szamlalok.py --file x.csv   # helyi fájlból (teszteléshez)

Az oldalak <!-- SZAMLALOK:START --> és <!-- SZAMLALOK:END --> közötti részét írja újra.
A kártyán a végső szám áll (JS nélkül is helyes); a feltekerődő animációt a script.js
(initCounters) adja a data-count attribútum alapján.
Hibás táblázat esetén hibával leáll, és semmit nem módosít.
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common

# oldal -> a blokk behúzása
PAGES = {'index.html': ' ' * 8, 'rolunk.html': ' ' * 8}
SNAPSHOT = os.path.join(common.ROOT, 'data', 'szamlalok.csv')

COLUMNS = {'label': 'felirat', 'number': 'szám', 'visible': 'megjelenjen'}


def format_number(number):
    """Magyar ezres tagolás nem törő szóközzel: 1200 -> 1&nbsp;200."""
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
    args, env_name = common.get_args('SZAMLALOK_CSV_URL')
    csv_text = common.fetch(args, env_name, sheet='Számlálók')
    table = common.read_table(csv_text, COLUMNS, required=['label', 'number', 'visible'])

    cards = []
    for line_number, row in table:
        if row['visible'].lower() == 'nem':
            continue
        if not row['label']:
            common.warn(f'{line_number}. sor: nincs megadva a felirat, kihagyva.')
            continue
        digits = re.sub(r'[\s .,]', '', row['number'])
        if not digits.isdigit():
            common.warn(f'{line_number}. sor: a szám nem értelmezhető ("{row["number"]}"), kihagyva.')
            continue
        cards.append((row['label'], int(digits)))
    if not cards:
        common.fail('Egyetlen megjelenő számláló sincs a táblázatban, ezért nem írom felül az oldalakat.')

    changed = []
    for page, indent in PAGES.items():
        if common.replace_block(os.path.join(common.ROOT, page), 'SZAMLALOK', build_block(cards, indent), indent):
            changed.append(page)
    common.save_snapshot(SNAPSHOT, csv_text)
    print(f'{len(cards)} számláló; frissített oldalak: {", ".join(changed) if changed else "nincs"}.')


if __name__ == '__main__':
    main()
