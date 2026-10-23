"""Shared helpers for the sync scripts that build page sections from Google Sheets.

Used by most tools/sync_*.py scripts (sync_programs.py has its own copy of the basics but
follows the same rules). Log messages stay in Hungarian: they are read by the sheet editors.
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


# Two shared workbooks, each published as a whole in Excel (.xlsx) format. When the URL is set,
# the scripts read their own sheet from it and ignore the old per-sheet CSV URLs.
#   TEAM_SHEET_URL    – "Csapat adatai" (edited by a small group): Csapatvezetés, Rajok, Számlálók, Táborok
#   LEADERS_SHEET_URL – "Vezetői táblázat" (edited by every leader): Programok, Értesítők, Eszközök,
#                       Eszközök kapcsolattartója
TEAM_SHEET_ENV = 'TEAM_SHEET_URL'
LEADERS_SHEET_ENV = 'LEADERS_SHEET_URL'


def get_args(env_name):
    parser = argparse.ArgumentParser()
    parser.add_argument('--url')
    parser.add_argument('--file')
    parser.add_argument('--xlsx', help='local .xlsx copy of the shared workbook')
    return parser.parse_args(), env_name


def _cell_csv(value):
    import datetime
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        if value.date() == datetime.date(1899, 12, 30):   # time only (day zero of Excel dates)
            return value.strftime('%H:%M')
        if value.time() != datetime.time(0, 0):
            return value.strftime('%Y.%m.%d. %H:%M')
        value = value.date()
    if isinstance(value, datetime.time):
        return value.strftime('%H:%M')
    if isinstance(value, datetime.date):
        return value.strftime('%Y.%m.%d.')
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def xlsx_sheet_as_csv(data, sheet_name):
    """Converts one sheet of the shared workbook to CSV text (the same as a per-sheet CSV export)."""
    try:
        import openpyxl
    except ImportError:
        fail('Hiányzik az openpyxl csomag (pip install openpyxl).')
    try:
        book = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as error:
        fail(f'A közös táblázat nem olvasható Excel-fájlként ({error}). A TELJES dokumentum van közzétéve, '
             'Microsoft Excel (.xlsx) formátumban?')
    sheet = next((ws for ws in book.worksheets if ws.title.strip().lower() == sheet_name.lower()), None)
    if sheet is None:
        fail(f'A közös táblázatban nincs "{sheet_name}" lap. Valaki átnevezte vagy törölte?')
    rows = [[_cell_csv(v) for v in row] for row in sheet.iter_rows(values_only=True)]
    while rows and not any(cell.strip() for cell in rows[-1]):   # trailing empty rows (as in the CSV export)
        rows.pop()
    out = io.StringIO()
    csv.writer(out, lineterminator='\n').writerows(rows)
    return out.getvalue().rstrip('\n')


_BOOKS = {}


def shared_sheet_csv(args, sheet, book_env):
    """One sheet of the shared workbook (local --xlsx file or the URL in book_env) as CSV text, or
    None when no shared workbook is configured. The download is reused within one run."""
    if getattr(args, 'file', None):
        return None
    path, url = getattr(args, 'xlsx', None), os.environ.get(book_env)
    if not path and not url:
        return None
    key = path or url
    if key not in _BOOKS:
        if path:
            with open(path, 'rb') as handle:
                _BOOKS[key] = handle.read()
        else:
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    _BOOKS[key] = response.read()
            except Exception as error:
                fail(f'A közös táblázat letöltése nem sikerült: {error}')
    return xlsx_sheet_as_csv(_BOOKS[key], sheet)


def fetch(args, env_name, sheet=None, book_env=TEAM_SHEET_ENV):
    """The sheet's content as CSV text. Order: --file (CSV) · the shared workbook (--xlsx or the
    URL in book_env, when the script passes its sheet name) · the old per-sheet CSV URL."""
    if sheet:
        text = shared_sheet_csv(args, sheet, book_env)
        if text is not None:
            return text
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


SHEET_ERRORS = ('#ERROR!', '#NAME?', '#REF!', '#VALUE!', '#N/A', '#DIV/0!', '#NUM!', '#NULL!')


def is_sheet_error(value):
    """A Google Sheets error value (e.g. "+36 …" parsed as a formula becomes #ERROR!) – never publish it."""
    return value.strip().upper() in SHEET_ERRORS


def read_table(csv_text, columns, required):
    """Finds column indexes from the header row (compares the START of each header, lowercased;
    a key may accept several prefixes as a tuple) and returns the rows as dicts:
    [(line number, {key: value}), ...]."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        fail('A táblázat üres.')
    lowered = [cell.strip().lower() for cell in rows[0]]
    index = {}
    for key, prefix in columns.items():
        prefixes = prefix if isinstance(prefix, tuple) else (prefix,)   # several accepted headers
        for i, cell in enumerate(lowered):
            if cell.startswith(prefixes):
                index[key] = i
                break
    missing = [(lambda p: p if isinstance(p, str) else p[0])(columns[key]) for key in required if key not in index]
    if missing:
        fail('A táblázat fejlécéből hiányzik: ' + ', '.join(missing) + '. Valaki átírta az első sort?')
    result = []
    for line_number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        record = {}
        for key, i in index.items():
            value = row[i].strip() if i < len(row) else ''
            if is_sheet_error(value):
                warn(f'{line_number}. sor, "{rows[0][i].strip()}" oszlop: a cellában táblázathiba van ({value}), '
                     'üresnek veszem. (Telefonszámnál a "+" jel okozza: állítsd az oszlopot Egyszerű szövegre, '
                     'vagy írd így: \'+36 …)')
                value = ''
            record[key] = value
        result.append((line_number, record))
    return result


def fix_phone(phone):
    """If the sheet turned "+36 …" into a number (e.g. 36707582659), returns it in readable form
    (+36 70 758 2659). Any other input is returned unchanged."""
    raw = phone.strip()
    if re.fullmatch(r'36\d{9}', raw):          # mobile / regional: 36 + 2-digit area code + 7 digits
        return f'+36 {raw[2:4]} {raw[4:7]} {raw[7:]}'
    if re.fullmatch(r'361\d{7}', raw):         # Budapest: 36 1 + 7 digits
        return f'+36 1 {raw[3:6]} {raw[6:]}'
    return phone


def contact_lines(email, phone):
    """HTML links for an e-mail address and a phone number (both optional)."""
    lines = []
    if email:
        if '@' in email:
            lines.append(f'<a class="inline-link" href="mailto:{html.escape(email, quote=True)}">{html.escape(email)}</a>')
        else:
            warn(f'Az e-mail cím nem tűnik érvényesnek, kihagyva: "{email}"')
    if phone:
        phone = fix_phone(phone)
        digits = re.sub(r'[^\d+]', '', phone)
        if len(re.sub(r'\D', '', digits)) >= 6:
            lines.append(f'<a class="inline-link" href="tel:{digits}">{html.escape(phone)}</a>')
        else:
            lines.append(html.escape(phone))
    return lines


def replace_block(page_path, marker, body, indent):
    """Replaces the part between <!-- MARKER:START ... --> and <!-- MARKER:END --> in the page.
    Returns True if the page changed."""
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
