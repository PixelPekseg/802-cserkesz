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
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
in_actions = os.environ.get('GITHUB_ACTIONS') == 'true'


def _log_text(message):
    """Messages often quote sheet cells. In GitHub Actions a line starting with "::" is a workflow
    command, so the data is escaped the official way (%, CR, LF): a cell cannot inject commands."""
    text = str(message)
    if in_actions:
        text = text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    return text


def warn(message):
    print(('::warning::' if in_actions else 'FIGYELEM: ') + _log_text(message))


def fail(message):
    print(('::error::' if in_actions else 'HIBA: ') + _log_text(message))
    sys.exit(1)


# ---------- downloads ----------

MAX_DOWNLOAD = 30 * 1024 * 1024   # a workbook or an image is far smaller; protects against runaway responses
USER_AGENT = '802-cserkesz-sync (+https://github.com/PixelPekseg/802-cserkesz)'


class DownloadError(Exception):
    """A download failed. The message never contains the URL (it may carry an API key)."""


def download(url, max_bytes=MAX_DOWNLOAD, timeout=30, attempts=3):
    """Downloads an https URL and returns the bytes. Temporary errors (network, timeout, 5xx, 429)
    are retried with a growing pause; permanent ones (other 4xx) fail at once."""
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise DownloadError('csak https:// címről töltök le')
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise DownloadError(f'a válasz nagyobb, mint {max(1, max_bytes // 1024)} kB')
            return data
        except urllib.error.HTTPError as error:
            reason = f'HTTP {error.code}'
            if error.code < 500 and error.code != 429:
                raise DownloadError(reason) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            reason = getattr(error, 'reason', None) or type(error).__name__
            if isinstance(reason, ssl.SSLError):   # a certificate problem does not go away by retrying
                raise DownloadError(f'SSL-hiba: {reason}') from None
        if attempt < attempts:
            time.sleep(3 * attempt)
    raise DownloadError(f'{reason} ({attempts} próbálkozás után)')


def safe_url(url, hosts, path_prefix=''):
    """The URL if it is https and points to one of the allowed hosts (and path), otherwise ''.
    Links typed into a sheet are checked with this before they reach the page."""
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme != 'https' or (parts.hostname or '').lower() not in hosts:
        return ''
    if path_prefix and not parts.path.startswith(path_prefix):
        return ''
    return url.strip()


# ---------- files ----------

def _write_atomic(path, data, mode):
    """Writes to a temporary file in the same folder, then swaps it in: an interrupted run never
    leaves a half-written page, image or state file behind."""
    folder = os.path.dirname(path) or '.'
    os.makedirs(folder, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=folder, prefix='.tmp-')
    try:
        with os.fdopen(handle, mode, **({'encoding': 'utf-8'} if 'b' not in mode else {})) as out:
            out.write(data)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def write_text(path, text):
    _write_atomic(path, text, 'w')


def write_bytes(path, data):
    _write_atomic(path, data, 'wb')


# Two shared workbooks, each published as a whole in Excel (.xlsx) format. When the URL is set,
# the scripts read their own sheet from it and ignore the old per-sheet CSV URLs.
#   TEAM_SHEET_URL    – "Csapat adatai" (edited by a small group): Csapatvezetés, Rajok, Számlálók, Táborok
#   LEADERS_SHEET_URL – "Vezetői táblázat" (edited by every leader): Programok, Értesítők, Eszközök,
#                       Eszközök kapcsolattartója, Médiás kapcsolat (the latter only for the reminder e-mails)
TEAM_SHEET_ENV = 'TEAM_SHEET_URL'
LEADERS_SHEET_ENV = 'LEADERS_SHEET_URL'


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', help='local CSV export of the sheet (for testing)')
    parser.add_argument('--xlsx', help='local .xlsx copy of the shared workbook')
    return parser.parse_args()


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
                _BOOKS[key] = download(url)
            except DownloadError as error:
                fail(f'A közös táblázat letöltése nem sikerült: {error}')
    return xlsx_sheet_as_csv(_BOOKS[key], sheet)


def fetch(args, sheet, book_env=TEAM_SHEET_ENV):
    """The sheet's content as CSV text: from --file (a local CSV, for testing), otherwise from the
    shared workbook (--xlsx or the URL in book_env)."""
    if args.file:
        with open(args.file, encoding='utf-8-sig') as handle:
            text = handle.read()
    else:
        text = shared_sheet_csv(args, sheet, book_env)
        if text is None:
            fail(f'Nincs megadva a közös táblázat címe ({book_env} vagy --xlsx).')
    return text.replace('\r\n', '\n').replace('\r', '\n')


# Values of the "Megjelenjen?" column that hide a row (case, spaces and a trailing dot ignored:
# "nem", "Nem.", " NEM " …). Anything else – also an empty cell – shows the row.
HIDDEN_VALUES = {'nem', 'no', 'n', 'false', 'hamis', '0'}


def is_hidden(value):
    return (value or '').strip().rstrip('.!').strip().lower() in HIDDEN_VALUES


SHEET_ERRORS = ('#ERROR!', '#NAME?', '#REF!', '#VALUE!', '#N/A', '#DIV/0!', '#NUM!', '#NULL!')


def is_sheet_error(value):
    """A Google Sheets error value (e.g. "+36 …" parsed as a formula becomes #ERROR!) – never publish it."""
    return value.strip().upper() in SHEET_ERRORS


HEADER_SEARCH_ROWS = 5   # the header may sit a few rows down (an empty or title row inserted above it)


def _match_columns(header, columns):
    lowered = [cell.strip().lower() for cell in header]
    index = {}
    for key, prefix in columns.items():
        prefixes = prefix if isinstance(prefix, tuple) else (prefix,)   # several accepted headers
        for i, cell in enumerate(lowered):
            if cell.startswith(prefixes):
                index[key] = i
                break
    return index


def find_header(rows, columns, required):
    """(header row index, {key: column index}). Looks at the first few rows, so a row inserted
    above the header by mistake does not break the sync; fails if no row has every required column."""
    best = None
    for n, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        index = _match_columns(row, columns)
        if all(key in index for key in required):
            if n:
                warn(f'A fejléc a(z) {n + 1}. sorban van (fölötte üres vagy más sor áll); így is beolvasom, '
                     'de érdemes a fölötte lévő sort törölni.')
            return n, index
        if best is None or len(index) > len(best[1]):
            best = (n, index)
    index = best[1] if best else {}
    missing = [(lambda p: p if isinstance(p, str) else p[0])(columns[key]) for key in required if key not in index]
    fail('A táblázat fejlécéből hiányzik: ' + ', '.join(missing) + '. Valaki átírta vagy törölte a fejléc sorát?')


def read_table(csv_text, columns, required):
    """Finds column indexes from the header row (compares the START of each header, lowercased;
    a key may accept several prefixes as a tuple) and returns the rows as dicts:
    [(line number, {key: value}), ...]."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not any(any(cell.strip() for cell in row) for row in rows):
        fail('A táblázat üres.')
    header_row, index = find_header(rows, columns, required)
    result = []
    for line_number, row in enumerate(rows[header_row + 1:], start=header_row + 2):
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
    """A Hungarian number written without spaces (+36707582659, 06707582659, or 36707582659 when the
    sheet turned "+36 …" into a number) in readable form: +36 70 758 2659. Any other input (e.g.
    already spaced, or foreign) is returned unchanged."""
    raw = phone.strip()
    if re.fullmatch(r'(?:\+36|06)\d{8,9}', raw):
        raw = '36' + raw[3:] if raw.startswith('+') else '36' + raw[2:]
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
        write_text(page_path, new_page)
        return True
    return False


def save_snapshot(path, text):
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
    if old != text:
        write_text(path, text)
