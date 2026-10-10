"""Közös segédfüggvények a Google Táblázatból (közzétett CSV) dolgozó frissítő szkriptekhez.

Használja: sync_taborok.py, sync_rajok.py
(a sync_programok.py önálló, ugyanezeket az elveket követi).
"""
import argparse
import csv
import html
import io
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
in_actions = os.environ.get('GITHUB_ACTIONS') == 'true'


def warn(message):
    print(('::warning::' if in_actions else 'FIGYELEM: ') + message)


def fail(message):
    print(('::error::' if in_actions else 'HIBA: ') + message)
    sys.exit(1)


def get_args(env_name):
    parser = argparse.ArgumentParser()
    parser.add_argument('--url')
    parser.add_argument('--file')
    return parser.parse_args(), env_name


def fetch(args, env_name):
    if args.file:
        with open(args.file, encoding='utf-8-sig') as handle:
            text = handle.read()
    else:
        url = args.url or os.environ.get(env_name)
        if not url:
            fail(f'Nincs megadva a CSV címe ({env_name} vagy --url).')
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                text = response.read().decode('utf-8-sig')
        except Exception as error:
            fail(f'A táblázat letöltése nem sikerült: {error}')
    return text.replace('\r\n', '\n').replace('\r', '\n')


def read_table(csv_text, columns, required):
    """A fejléc alapján oszlopindexeket keres (a fejléc ELEJÉT kisbetűsen hasonlítja), és
    a sorokat szótárakként adja vissza: [(sorszám, {kulcs: érték}), ...]."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        fail('A táblázat üres.')
    lowered = [cell.strip().lower() for cell in rows[0]]
    index = {}
    for key, prefix in columns.items():
        for i, cell in enumerate(lowered):
            if cell.startswith(prefix):
                index[key] = i
                break
    missing = [columns[key] for key in required if key not in index]
    if missing:
        fail('A táblázat fejlécéből hiányzik: ' + ', '.join(missing) + '. Valaki átírta az első sort?')
    result = []
    for line_number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        record = {key: (row[i].strip() if i < len(row) else '') for key, i in index.items()}
        result.append((line_number, record))
    return result


def contact_lines(email, phone):
    """E-mail és telefon HTML-hivatkozásai (mindkettő opcionális)."""
    lines = []
    if email:
        if '@' in email:
            lines.append(f'<a class="inline-link" href="mailto:{html.escape(email, quote=True)}">{html.escape(email)}</a>')
        else:
            warn(f'Az e-mail cím nem tűnik érvényesnek, kihagyva: "{email}"')
    if phone:
        digits = re.sub(r'[^\d+]', '', phone)
        if len(re.sub(r'\D', '', digits)) >= 6:
            lines.append(f'<a class="inline-link" href="tel:{digits}">{html.escape(phone)}</a>')
        else:
            lines.append(html.escape(phone))
    return lines


def replace_block(page_path, marker, body, indent):
    """A page-ben a <!-- MARKER:START ... --> és <!-- MARKER:END --> közötti részt cseréli.
    Igazat ad vissza, ha az oldal változott."""
    with open(page_path, encoding='utf-8') as handle:
        page = handle.read()
    pattern = re.compile(r'(<!-- %s:START[^\n]*-->\n)(.*?)(\n[ \t]*<!-- %s:END -->)' % (marker, marker), re.S)
    if not pattern.search(page):
        fail(f'A {os.path.basename(page_path)}-ben nem találom a {marker}:START / {marker}:END jelölőket.')
    new_page = pattern.sub(lambda m: m.group(1) + body + '\n\n' + indent + f'<!-- {marker}:END -->', page, count=1)
    if new_page != page:
        with open(page_path, 'w', encoding='utf-8') as handle:
            handle.write(new_page)
        return True
    return False


def save_snapshot(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
    if old != text:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
