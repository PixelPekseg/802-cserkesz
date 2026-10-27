#!/usr/bin/env python3
"""Updates the Tagdíj / Nagytábordíj / Kcs tábordíj (membership fee / summer camp fee / cub camp
fee) tabs of the Pénzügyek page (penzugyek.html) from one Google Sheet.

Sheets of the workbook: Leírás (guide, not read by the site) · Tagdíj · Nagytábordíj · Kcs tábordíj.
Each tab sheet holds four blocks below each other; a block starts with its title in column A
(ALAPADATOK, DÍJAK, RÉSZLETEK, KÖLTSÉGEK); for the table blocks the next row is the header:
  ALAPADATOK – two columns (Mező · Érték): Megjelenés kezdete, Megjelenés vége, Cím,
               Bevezető szöveg, Kiemelt mondat, Alapüzenet, ECSET kódok linkje,
               Támogatás űrlap linkje, Támogatás igénylésének határideje,
               Költségek címe / bevezetője / megjegyzése
  DÍJAK      – Kategória · Összeg · Részletezés · Magyarázat címe · Magyarázat · Megjelenjen?
               (the fee cards and the explanatory paragraphs below them; a row may hold a fee and
               an explanation, independently. The explanation title goes in bold at the start.)
  RÉSZLETEK  – Cím · Befizetési határidő · Összeg · Megjegyzés · Megjelenjen?
  KÖLTSÉGEK  – Tétel · Összeg (Ft) · Megjelenjen?   (left empty, the section is not shown)
The workbook must be published as a whole in Microsoft Excel (.xlsx) format, so a single URL
is needed (FEES_SHEET_URL).

A tab's content is shown between "Megjelenés kezdete" and "Megjelenés vége" (the end day still
counts; empty end = no end); outside that, or without a start, only the Alapüzenet (default
message). script.js (updateFees) re-checks the period on every page load, so no new run is needed.
The bank details, the payment-reference warning and the ECSET box text are the same on every tab
and fixed in the code (the account number deliberately cannot be changed from the sheet).

In text cells: new line = new paragraph, **text** = bold.

Usage:
    python tools/sync_fees.py                 # from the FEES_SHEET_URL environment variable
    python tools/sync_fees.py --file p.xlsx   # from a local file

Rewrites the part of penzugyek.html between <!-- FEES_<TAB>:START/END -->. Without a URL it
changes nothing. A broken tab sheet leaves that tab unchanged, the others are still updated, and
the run ends with an error.
"""
import argparse
import datetime
import html
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common

PAGE = os.path.join(common.ROOT, 'penzugyek.html')
TABS = [
    # (key, name of the sheet, marker)
    ('tagdij', 'Tagdíj', 'FEES_MEMBERSHIP'),
    ('nagytabor', 'Nagytábordíj', 'FEES_SUMMER_CAMP'),
    ('kcstabor', 'Kcs tábordíj', 'FEES_CUB_CAMP'),
]
ENV_NAME = 'FEES_SHEET_URL'
SNAPSHOT_NAMES = {'tagdij': 'fees_membership', 'nagytabor': 'fees_summer_camp', 'kcstabor': 'fees_cub_camp'}
# the tab's name in the title banner (script.js writes data-label into the h1)
LABELS = {'tagdij': 'Tagdíj', 'nagytabor': 'Nagytábordíj', 'kcstabor': 'Kcs tábordíj'}
INDENT = ' ' * 6

# Fields of the ALAPADATOK block (by the START of the Mező column, lowercased)
FIELDS = {
    'from': 'megjelenés kezdete', 'until': 'megjelenés vége', 'title': 'cím',
    'intro': 'bevezető', 'key': 'kiemelt', 'empty': 'alapüzenet',
    'ecset': 'ecset', 'form': 'támogatás', 'form_deadline': 'támogatás igénylés', 'costs_title': 'költségek címe',
    'costs_intro': 'költségek bevezető', 'costs_note': 'költségek megjegyzés',
}
# the table blocks: key -> (block title, columns by the START of the header)
BLOCKS = {
    'prices': ('Díjak', {'name': 'kategória', 'amount': 'összeg', 'split': 'részletezés',
                         'rule_title': 'magyarázat címe', 'rule_text': 'magyarázat', 'visible': 'megjelenjen'}),
    'items': ('Részletek', {'title': 'cím', 'deadline': 'befizetési', 'amount': 'összeg', 'note': 'megjegyzés',
                            'visible': 'megjelenjen'}),
    'costs': ('Költségek', {'name': 'tétel', 'amount': 'összeg', 'visible': 'megjelenjen'}),
}
DEFAULT_EMPTY = {'tagdij': 'Jelenleg nincs tagdíj befizetési időszak!'}
MONTHS = ['január', 'február', 'március', 'április', 'május', 'június', 'július',
          'augusztus', 'szeptember', 'október', 'november', 'december']

COPY_ICON = ('<svg class="icon-copy" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/>'
             '<path d="M5 15V6a2 2 0 0 1 2-2h9"/></svg><svg class="icon-check" viewBox="0 0 24 24" aria-hidden="true">'
             '<path d="M5 13l4 4L19 7"/></svg>')


class SheetError(Exception):
    pass


# ---------- reading ----------

def cell_text(value):
    """Cell value as text (dates as YYYY.MM.DD., whole numbers without decimals)."""
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        value = value.date()
    if isinstance(value, datetime.date):
        return value.strftime('%Y.%m.%d.')
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).replace('\r\n', '\n').replace('\r', '\n').strip()
    return '' if common.is_sheet_error(text) else text


def load_workbook(data):
    try:
        import openpyxl
    except ImportError:
        common.fail('Hiányzik az openpyxl csomag (pip install openpyxl).')
    try:
        return openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as error:
        raise SheetError(f'a letöltött fájl nem olvasható Excel-táblázatként ({error}). '
                         'Biztosan a TELJES dokumentum van közzétéve, Microsoft Excel (.xlsx) formátumban?')


def find_sheet(book, name):
    for sheet in book.worksheets:
        if sheet.title.strip().lower() == name.lower():
            return sheet
    return None


BLOCK_TITLES = {'alapadatok': 'fields', 'díjak': 'prices', 'részletek': 'items', 'költségek': 'costs'}


def split_blocks(sheet):
    """Splits a tab sheet's rows into blocks: {'fields': [rows], 'prices': [header, rows…], …}."""
    blocks, current = {}, None
    for row in sheet.iter_rows(values_only=True):
        cells = [cell_text(v) for v in row]
        first = cells[0].strip().rstrip(':').strip().lower() if cells else ''   # "Alapadatok:" works too
        if first in BLOCK_TITLES and not any(cells[1:]):
            current = BLOCK_TITLES[first]
            blocks[current] = []
            continue
        if current and any(cells):
            blocks[current].append(cells)
    return blocks


def read_fields(rows):
    if rows is None:
        raise SheetError('nincs ALAPADATOK blokk (az A oszlopban kell lennie a címének).')
    fields = {key: '' for key in FIELDS}
    for cells in rows:
        label = cells[0].lower()
        value = cells[1] if len(cells) > 1 else ''
        # the longer prefix wins (e.g. "költségek címe" must not match "cím")
        matches = [key for key, prefix in FIELDS.items() if label.startswith(prefix)]
        if matches:
            key = max(matches, key=lambda k: len(FIELDS[k]))
            fields[key] = value
    return fields


def read_rows(rows, block_name, columns):
    """Rows of a table block as dicts; rows with "Megjelenjen?" = nem are skipped.
    A missing or empty block = empty list."""
    if not rows:
        return []
    header = [c.lower() for c in rows[0]]
    index = {}
    # the longer prefix picks first (e.g. "magyarázat címe" must not match "magyarázat")
    for key, prefix in sorted(columns.items(), key=lambda item: -len(item[1])):
        for i, cell in enumerate(header):
            if cell.startswith(prefix) and i not in index.values():
                index[key] = i
                break
    missing = [columns[k] for k in columns if k not in index and k != 'visible']
    if missing:
        raise SheetError(f'a {block_name.upper()} blokk fejlécéből hiányzik: {", ".join(missing)}.')
    result = []
    for row in rows[1:]:
        record = {key: (row[i] if i < len(row) else '') for key, i in index.items()}
        if not any(v for k, v in record.items() if k != 'visible'):
            continue
        if common.is_hidden(record.get('visible', '')):
            continue
        result.append(record)
    return result


def parse_date(text):
    match = re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', text or '')
    if not match:
        return None
    try:
        return datetime.date(*map(int, match.groups()))
    except ValueError:
        return None


def nice_date(text):
    """2026.11.30. -> 2026. november 30. (returns the input unchanged if it is not a date)."""
    day = parse_date(text)
    if not day and re.search(r'\d{4}\D+\d{1,2}\D+\d{1,2}', text or ''):
        # looks like a date but is not one (e.g. 2026.11.31.): shown as typed, which stands out
        common.warn(f'Nem létező dátum: "{text}" (pl. a novembernek csak 30 napja van). Így írom ki, '
                    'ahogy a táblázatban áll; javítsd a táblázatban.')
    return f'{day.year}. {MONTHS[day.month - 1]} {day.day}.' if day else text


def money(text):
    """Bare number -> "15 000 Ft"; any other input stays as it is."""
    digits = text.replace(' ', '').replace(' ', '')
    if re.fullmatch(r'\d+', digits):
        return f'{int(digits):,}'.replace(',', ' ') + ' Ft'
    return text


# Links typed into the sheet may only point here (anything else is dropped with a warning):
# the ECSET list is a Drive/Docs file, the support form a Google Form (it is embedded in the page).
ECSET_HOSTS = {'drive.google.com', 'docs.google.com'}
FORM_HOSTS = {'docs.google.com'}


def check_link(text, what, hosts, path_prefix=''):
    if text and not common.safe_url(text, hosts, path_prefix):
        common.warn(f'A(z) {what} nem engedélyezett cím ({", ".join(sorted(hosts))}{path_prefix}…), kihagyom: "{text}"')
        return ''
    return text.strip()


# ---------- HTML ----------

def esc(text):
    return html.escape(text, quote=True)


def rich(text):
    """Escaped text, with **bold** markup."""
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', esc(text))


def paragraphs(text):
    return [rich(p.strip()) for p in text.split('\n') if p.strip()]


def copy_value(label, value, copy, mono=False, aria=None):
    aria = aria or label
    cls = 'bank-value bank-number' if mono else 'bank-value'
    return (f'              <p class="bank-label">{label}</p>\n'
            f'              <div class="bank-copy">\n'
            f'                <p class="{cls}">{esc(value)}</p>\n'
            f'                <button class="copy-btn" type="button" data-copy="{esc(copy)}" data-copy-label="{esc(aria)}" '
            f'aria-label="{esc(aria)} másolása" title="Másolás">{COPY_ICON}</button>\n'
            f'              </div>')


def render_pay(ecset_link):
    """Bank details + payment-reference warning + ECSET box: the same on every tab."""
    ecset = ''
    if ecset_link:
        ecset = f'''

            <div class="fee-box fee-ecset">
              <div>
                <h3>ECSET kód</h3>
                <p>A gyermek ECSET kódját a szülőkkel megosztott névsorban találja.</p>
                <p class="fee-box-note">
                  A fájlt csak akkor tudja megnyitni, ha azzal az e-mail-címmel van bejelentkezve
                  a Google-fiókjába, amelyik a csapat levelezőlistáján is szerepel.
                </p>
              </div>
              <a class="btn btn-primary" href="{esc(ecset_link)}" target="_blank" rel="noopener noreferrer">ECSET kódok megnyitása</a>
            </div>'''
    return f'''          <div class="fee-pay">
            <div class="bank-card">
              <h3>Banki átutalás az egyesület számlájára</h3>
{copy_value('Kedvezményezett neve', 'Gödöllői Cserkészetért Egyesület', 'Gödöllői Cserkészetért Egyesület')}
{copy_value('Számlaszám', '1620 0223 1007 7922 0000 0000', '162002231007792200000000', mono=True)}
{copy_value('vagy másodlagos banki azonosító', '+36204924970', '+36204924970', mono=True, aria='Másodlagos banki azonosító')}
              <p class="bank-label">Közlemény</p>
              <p class="bank-value">„Adomány” + ECSET kód</p>
            </div>

            <div class="fee-box fee-warning">
              <h3>Fontos: csak ez a két adat legyen a közleményben!</h3>
              <p>
                A közleménybe az „Adomány” szót és a gyermek ECSET kódját írja, ezeken kívül
                semmilyen más adatot ne adjon meg.
              </p>
              <p class="fee-example">Példa a közleményre: <strong>Adomány AAAAAA-1</strong></p>
              <ul>
                <li>Ha hiányzik az „Adomány” szó, a pénzt visszautaljuk, mert csak adományt fogadhatunk el.</li>
                <li>Ha az ECSET kód hiányzik vagy nem a megfelelő formában szerepel, a rendszer nem ismeri fel a befizetést, és a pénzt szintén visszautaljuk.</li>
                <li>A visszautalás miatt mindkét esetben 1 000 Ft plusz költséget számolunk fel.</li>
              </ul>
            </div>{ecset}
          </div>
'''


def render_form(form_link, deadline=''):
    """Support request: embedded form; script.js only loads its src when the tab is visible.
    At 23:59 on the day AFTER the deadline the form (with the deadline and the link) disappears and
    the .fee-form-closed message takes its place (script.js updateFees; here too, by the run time)."""
    base = re.sub(r'\?.*$', '', form_link)
    embed = base + '?embedded=true' if base.endswith('/viewform') else form_link
    day = parse_date(deadline)
    until = f' data-until="{day.isoformat()}"' if day else ''
    closed = bool(day) and datetime.datetime.now() >= datetime.datetime.combine(
        day + datetime.timedelta(days=1), datetime.time(23, 59))
    deadline_line = (f'              <p class="fee-form-deadline">Igénylési határidő: <strong>{esc(nice_date(deadline))}</strong></p>\n'
                     if deadline else '')
    closed_text = ''
    if day:
        closed_text = (f'\n            <p class="fee-form-closed"{"" if closed else " hidden"}>A támogatási igények leadási határideje '
                       f'{MONTHS[day.month - 1]} {day.day}. volt, sajnos már nem áll módunkban támogatási igényeket befogadni.</p>')
    return f'''          <div class="fee-form"{until}>
            <h3>Támogatás igénylése</h3>
            <div class="fee-form-open"{" hidden" if closed else ""}>
{deadline_line}              <p>
                A csapat minden évben támogatást oszt a tábordíjhoz és a tagdíjhoz az arra jelentkező
                családoknak. Amennyiben a befizetés megterhelő Önöknek, kérjük, nyugodtan jelezzék
                az alábbi űrlap kitöltésével.
              </p>
              <div class="fee-form-frame">
                <iframe data-src="{esc(embed)}" title="Támogatás igénylése (Google Űrlap)" loading="lazy" sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox">Betöltés…</iframe>
              </div>
              <p class="fee-form-link">Nem jelenik meg az űrlap? <a class="inline-link" href="{esc(form_link)}" target="_blank" rel="noopener noreferrer">Megnyitás új lapon</a></p>
            </div>{closed_text}
          </div>
'''


def render_tab(key, data, today):
    f = data['fields']
    empty = f['empty'] or DEFAULT_EMPTY.get(key, 'Jelenleg nincs tábordíj befizetési időszak!')
    start, end = parse_date(f['from']), parse_date(f['until'])
    if f['from'] and not start:
        common.warn(f'{key}: a Megjelenés kezdete nem dátum ("{f["from"]}"), csak az alapüzenet jelenik meg.')
    if f['until'] and not end:
        common.warn(f'{key}: a Megjelenés vége nem dátum ("{f["until"]}"), nincs vége az időszaknak.')
    if start and end and end < start:
        common.warn(f'{key}: a Megjelenés vége ({f["until"]}) korábbi, mint a kezdete ({f["from"]}), '
                    'így a fül tartalma soha nem látszana; csak az alapüzenet jelenik meg.')
    if start and not f['title']:
        common.warn(f'{key}: nincs megadva a Cím, ezért csak az alapüzenet jelenik meg.')
    has_content = bool(start and f['title'] and not (end and end < start))
    window = ''
    if has_content:
        window = f' data-from="{start.isoformat()}"' + (f' data-until="{end.isoformat()}"' if end else '')
    active = has_content and start <= today and (not end or today <= end)

    out = [f'<div class="fee-panel" id="panel-{key}" data-tab="{key}" data-label="{LABELS[key]}"{window}>']
    if not has_content:
        out.append('        <div class="fee-content" hidden></div>')
    else:
        out.append('        <div class="fee-content"' + ('' if active else ' hidden') + '>')
        # 1. title, introduction, highlighted sentence
        out.append('          <div class="fee-intro">')
        out.append(f'            <h2>{esc(f["title"])}</h2>')
        out += [f'            <p>{p}</p>' for p in paragraphs(f['intro'])]
        out.append('          </div>\n')
        if f['key']:
            out.append(f'          <p class="fee-key">{rich(f["key"])}</p>\n')
        # 2. fee cards
        prices = [row for row in data['prices'] if row.get('name')]
        rules = [row for row in data['prices'] if row.get('rule_text')]
        if prices:
            out.append('          <ul class="price-grid">')
            for row in prices:
                split = f'<span class="price-split">{esc(money(row.get("split", "")))}</span>' if row.get('split') else ''
                out.append(f'            <li><span class="price-name">{esc(row["name"])}</span>'
                           f'<span class="price-amount">{esc(money(row["amount"]))}</span>{split}</li>')
            out.append('          </ul>\n')
        # 3. fee card explanations
        if rules:
            out.append('          <div class="fee-rules">')
            for row in rules:
                for i, p in enumerate(paragraphs(row['rule_text'])):
                    title = f'<strong>{esc(row["rule_title"].rstrip(":"))}:</strong> ' if row.get('rule_title') and i == 0 else ''
                    out.append(f'            <p>{title}{p}</p>')
            out.append('          </div>\n')
        # 4. instalments
        if data['items']:
            out.append('          <div class="fee-items">')
            for row in data['items']:
                note = f'\n              <p class="fee-item-note">{rich(row["note"])}</p>' if row.get('note') else ''
                out.append(f'''            <div class="fee-item">
              <h3>{esc(row["title"])}</h3>
              <dl class="fee-facts">
                <div><dt>Befizetési határidő</dt><dd>{esc(nice_date(row.get("deadline", "")))}</dd></div>
                <div><dt>Összeg</dt><dd>{esc(money(row.get("amount", "")))}</dd></div>
              </dl>{note}
            </div>''')
            out.append('          </div>\n')
        # 5. fixed cards
        out.append(render_pay(f['ecset']))
        # 6. costs
        costs = []
        for row in data['costs']:
            digits = row['amount'].replace(' ', '').replace(' ', '').removesuffix('Ft')
            if not digits.isdigit():
                common.warn(f'{key}: a költség összege nem szám, kihagyom: "{row["name"]}" – "{row["amount"]}"')
                continue
            costs.append((row['name'], int(digits)))
        total = sum(v for _, v in costs)
        if costs and total:
            out.append('          <div class="fee-costs">')
            out.append(f'            <h3>{esc(f["costs_title"] or "Mire fordítjuk a befizetéseket?")}</h3>')
            out += [f'            <p>{p}</p>' for p in paragraphs(f['costs_intro'])]
            out.append('            <ul class="cost-list">')
            for name, value in costs:
                out.append(f'''              <li style="--share:{round(value / total * 100)}%">
                <span class="cost-name">{esc(name)}</span>
                <span class="cost-amount">{money(str(value))}</span>
                <span class="cost-bar" aria-hidden="true"></span>
              </li>''')
            out.append('            </ul>')
            out.append(f'            <p class="cost-total">Összesen évente: <strong>{money(str(total))}</strong></p>')
            out += [f'            <p class="cost-note">{p}</p>' for p in paragraphs(f['costs_note'])]
            out.append('          </div>\n')
        # 7. support request
        if f['form']:
            if not f['form_deadline']:
                common.warn(f'{key}: nincs megadva a támogatás igénylésének határideje.')
            elif not parse_date(f['form_deadline']):
                common.warn(f'{key}: a támogatás igénylésének határideje nem dátum ("{f["form_deadline"]}"), '
                            'ezért az űrlap nem zárul le magától. Írd így: 2026.11.15.')
            out.append(render_form(f['form'], f['form_deadline']))
        out[-1] = out[-1].rstrip('\n')
        out.append('        </div>')
    out.append(f'        <p class="fee-empty"' + (' hidden' if active else '') + f'>{esc(empty)}</p>')
    out.append('      </div>')
    return INDENT + '\n'.join(out)


# ---------- running ----------

def fetch_bytes(url):
    try:
        return common.download(url)
    except common.DownloadError as error:
        raise SheetError(f'a letöltés nem sikerült: {error}')


def read_tab(sheet):
    blocks = split_blocks(sheet)
    fields = read_fields(blocks.get('fields'))
    fields['ecset'] = check_link(fields['ecset'], 'ECSET kódok linkje', ECSET_HOSTS)
    fields['form'] = check_link(fields['form'], 'támogatás űrlap linkje', FORM_HOSTS, '/forms/')
    result = {'fields': fields}
    for key, (block_name, columns) in BLOCKS.items():
        result[key] = read_rows(blocks.get(key), block_name, columns)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', help='local .xlsx file')
    parser.add_argument('--today', help='for testing: YYYY-MM-DD')
    args = parser.parse_args()
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()

    url = os.environ.get(ENV_NAME)
    if not args.file and not url:
        common.warn(f'Nincs megadva a Pénzügyek táblázat címe ({ENV_NAME}), az oldal változatlan marad.')
        return
    try:
        book = load_workbook(open(args.file, 'rb').read() if args.file else fetch_bytes(url))
    except SheetError as error:
        common.fail(f'A Pénzügyek táblázat nem olvasható, az oldal változatlan maradt – {error}')

    updated, errors = [], []
    for key, sheet_name, marker in TABS:
        sheet = find_sheet(book, sheet_name)
        if sheet is None:
            errors.append(f'nincs "{sheet_name}" lap')
            continue
        try:
            data = read_tab(sheet)
            body = render_tab(key, data, today)
        except SheetError as error:
            errors.append(f'{sheet_name}: {error}')
            continue
        if common.replace_block(PAGE, marker, body, INDENT):
            updated.append(key)
        common.save_snapshot(os.path.join(common.ROOT, 'data', f'{SNAPSHOT_NAMES[key]}.json'),
                             json.dumps(data, ensure_ascii=False, indent=2) + '\n')

    print(f'Frissített fülek: {", ".join(updated) or "nincs"}.')
    if errors:
        common.fail('Hibás táblázat, ez a fül változatlan maradt – ' + ' | '.join(errors))


if __name__ == '__main__':
    main()
