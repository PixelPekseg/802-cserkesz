import datetime as dt

import pytest

import sync_fees as fees
from conftest import block, read_json, xlsx_bytes

TODAY = dt.date(2026, 10, 27)


def tab(fields=None, prices=None, items=None, costs=None, extra=()):
    """The rows of one tab sheet with the four blocks."""
    base = {'Megjelenés kezdete': dt.date(2026, 9, 1), 'Megjelenés vége': '2026.12.31.', 'Cím': '2026. évi tagdíj',
            'Bevezető szöveg': 'Kedves Szülők!\nMásodik **kiemelt** bekezdés', 'Kiemelt mondat': 'Fontos!',
            'Alapüzenet (az időszakon kívül)': 'Nincs most', 'ECSET kódok linkje': 'https://drive.google.com/file/d/x',
            'Támogatás űrlap linkje': 'https://docs.google.com/forms/d/e/1/viewform?usp=dialog',
            'Támogatás igénylésének határideje': '2026.11.15.', 'Költségek címe': 'Mire megy?',
            'Költségek bevezetője': 'A pénz…', 'Költségek megjegyzése': 'Köszönjük!'}
    base.update(fields or {})
    rows = [['ALAPADATOK'], ['Mező', 'Érték']] + [[k, v] for k, v in base.items() if v is not None]
    rows += [['DÍJAK:'], ['Kategória', 'Összeg', 'Részletezés', 'Magyarázat címe', 'Magyarázat', 'Megjelenjen?']]
    rows += prices if prices is not None else [['Tagdíj', '30000', '2 × 15 000 Ft', 'Testvér:', 'Kedvezmény\njár', 'igen'],
                                               ['', '', '', '', 'Csak magyarázat', ''], ['Rejtett', '1', '', '', '', 'nem']]
    rows += [['RÉSZLETEK'], ['Cím', 'Befizetési határidő', 'Összeg', 'Megjegyzés', 'Megjelenjen?']]
    rows += items if items is not None else [['1. részlet', '2026.04.01.', '15000', '**Egyben** is lehet', 'igen'],
                                             ['2. részlet', '2026.11.31.', '15 000 Ft', '', 'igen']]
    rows += [['KÖLTSÉGEK'], ['Tétel', 'Összeg (Ft)', 'Megjelenjen?']]
    rows += costs if costs is not None else [['Közművek', '4 600 000 Ft', 'igen'], ['Szövetség', '4000000', ''],
                                             ['Rossz', 'sok', 'igen']]
    return rows + list(extra)


@pytest.fixture
def workbook(paths, tmp_path):
    def make(**tabs):
        sheets = {'Leírás': [['útmutató']]}
        for key, name in (('tagdij', 'Tagdíj'), ('nagytabor', 'Nagytábordíj'), ('kcstabor', 'Kcs tábordíj')):
            if tabs.get(key, ()) is not None:
                sheets[name] = tabs.get(key) or tab()
        path = tmp_path / 'p.xlsx'
        path.write_bytes(xlsx_bytes(sheets))
        return path
    return make


def run(monkeypatch, path, today='2026-10-27'):
    monkeypatch.setattr('sys.argv', ['sync_fees.py', '--file', str(path), '--today', today])
    fees.main()


def test_full_tab(workbook, paths, monkeypatch, issues):
    run(monkeypatch, workbook())
    html = block(paths / 'penzugyek.html', 'FEES_MEMBERSHIP')
    assert 'data-from="2026-09-01" data-until="2026-12-31"' in html
    assert '<div class="fee-content">' in html                           # active today
    assert '<p>Második <strong>kiemelt</strong> bekezdés</p>' in html
    assert '<span class="price-amount">30 000 Ft</span>' in html and 'Rejtett' not in html
    assert '<p><strong>Testvér:</strong> Kedvezmény</p>' in html and '<p>Csak magyarázat</p>' in html
    assert 'data-deadline="2026-04-01"' in html and '2026. április 1.' in html
    assert '<dd>2026.11.31.</dd>' in html and 'data-deadline="2026-11-31"' not in html
    assert 'style="--share:53%"' in html and 'Összesen évente: <strong>8 600 000 Ft</strong>' in html
    assert 'viewform?embedded=true' in html and 'data-until="2026-11-15"' in html
    assert 'href="https://drive.google.com/file/d/x"' in html
    snapshot = read_json(paths / 'data' / 'fees_membership.json')
    assert snapshot['fields']['title'] == '2026. évi tagdíj'
    messages = ' '.join(i['message'] for i in issues())
    assert 'Nem létező dátum: "2026.11.31."' in messages and 'nem szám, kihagyom: "Rossz"' in messages


def test_outside_the_period_and_closed_form(workbook, paths, monkeypatch):
    run(monkeypatch, workbook(), today='2027-01-05')
    html = block(paths / 'penzugyek.html', 'FEES_MEMBERSHIP')
    assert '<div class="fee-content" hidden>' in html and '<p class="fee-empty">Nincs most</p>' in html
    assert '<div class="fee-form-open" hidden>' in html                # the deadline (Nov 15) has passed
    assert '<p class="fee-form-closed">A támogatási igények leadási határideje november 15. volt' in html


@pytest.mark.parametrize('fields, message, has_content', [
    ({'Megjelenés kezdete': 'szeptember'}, 'Megjelenés kezdete nem dátum', False),
    ({'Megjelenés vége': 'soha'}, 'Megjelenés vége nem dátum', True),
    ({'Megjelenés vége': '2026.08.01.'}, 'korábbi, mint a kezdete', False),
    ({'Cím': None}, 'nincs megadva a Cím', False),
    ({'Támogatás igénylésének határideje': None}, 'nincs megadva a támogatás igénylésének határideje', True),
    ({'Támogatás igénylésének határideje': 'nov. közepe'}, 'nem dátum ("nov. közepe")', True),
    ({'ECSET kódok linkje': 'https://evil.com/x'}, 'ECSET kódok linkje nem engedélyezett cím', True),
    ({'Támogatás űrlap linkje': 'https://docs.google.com/document/d/x'}, 'támogatás űrlap linkje nem engedélyezett', True),
])
def test_field_problems(workbook, paths, monkeypatch, issues, fields, message, has_content):
    run(monkeypatch, workbook(tagdij=tab(fields)))
    assert message in ' '.join(i['message'] for i in issues())
    html = block(paths / 'penzugyek.html', 'FEES_MEMBERSHIP')
    assert ('fee-intro' in html) is has_content


def test_default_empty_messages(workbook, paths, monkeypatch):
    run(monkeypatch, workbook(nagytabor=tab({'Megjelenés kezdete': None, 'Alapüzenet (az időszakon kívül)': None})))
    assert 'Jelenleg nincs tábordíj befizetési időszak!' in block(paths / 'penzugyek.html', 'FEES_SUMMER_CAMP')


def test_empty_blocks_and_no_costs(workbook, paths, monkeypatch):
    run(monkeypatch, workbook(tagdij=tab({'Támogatás űrlap linkje': None, 'ECSET kódok linkje': None},
                                         prices=[], items=[], costs=[['Nulla', '0', '']])))
    html = block(paths / 'penzugyek.html', 'FEES_MEMBERSHIP')
    assert 'price-grid' not in html and 'fee-items' not in html and 'fee-costs' not in html
    assert 'fee-form' not in html and 'fee-ecset' not in html and 'fee-pay' in html


def test_broken_tab_leaves_it_and_updates_the_others(workbook, paths, monkeypatch, issues):
    before = block(paths / 'penzugyek.html', 'FEES_SUMMER_CAMP')
    broken = [['Valami más'], ['DÍJAK'], ['Kategória']]
    with pytest.raises(SystemExit):
        run(monkeypatch, workbook(nagytabor=broken, kcstabor=None))
    assert block(paths / 'penzugyek.html', 'FEES_SUMMER_CAMP') == before
    assert 'fee-intro' in block(paths / 'penzugyek.html', 'FEES_MEMBERSHIP')
    message = issues()[-1]['message']
    assert 'Nagytábordíj: nincs ALAPADATOK blokk' in message and 'nincs "Kcs tábordíj" lap' in message


def test_missing_header_column(workbook, paths, monkeypatch, issues):
    rows = tab(prices=[])
    rows[rows.index(['DÍJAK:']) + 1] = ['Kategória', 'Részletezés']
    with pytest.raises(SystemExit):
        run(monkeypatch, workbook(tagdij=rows))
    assert 'a DÍJAK blokk fejlécéből hiányzik: összeg' in issues()[-1]['message']


def test_no_url_and_unreadable_file(paths, monkeypatch, tmp_path, issues):
    monkeypatch.setattr('sys.argv', ['sync_fees.py'])
    fees.main()
    assert 'FEES_SHEET_URL' in issues()[-1]['message']
    bad = tmp_path / 'x.xlsx'
    bad.write_bytes(b'nem xlsx')
    with pytest.raises(SystemExit):
        run(monkeypatch, bad)
    assert 'nem olvasható Excel-táblázatként' in issues()[-1]['message']


def test_download_error(paths, monkeypatch, issues):
    def broken(url):
        raise fees.common.DownloadError('HTTP 404')
    monkeypatch.setattr(fees.common, 'download', broken)
    monkeypatch.setenv('FEES_SHEET_URL', 'https://docs.google.com/x')
    monkeypatch.setattr('sys.argv', ['sync_fees.py'])
    with pytest.raises(SystemExit):
        fees.main()
    assert 'a letöltés nem sikerült: HTTP 404' in issues()[-1]['message']


@pytest.mark.parametrize('value, text', [
    (None, ''), (dt.datetime(2026, 1, 2, 10, 0), '2026.01.02.'), (dt.date(2026, 1, 2), '2026.01.02.'),
    (15000.0, '15000'), (2.5, '2.5'), ('  a\r\nb  ', 'a\nb'), ('#REF!', ''),
])
def test_cell_text(value, text):
    assert fees.cell_text(value) == text


@pytest.mark.parametrize('text, out', [('15000', '15 000 Ft'), ('15 000', '15 000 Ft'), ('15 000', '15 000 Ft'),
                                       ('2 × 15 000 Ft', '2 × 15 000 Ft'), ('', '')])
def test_money(text, out):
    assert fees.money(text) == out


def test_render_form_closed_after_the_day_after_the_deadline(monkeypatch):
    link = 'https://docs.google.com/forms/d/e/1/viewform'
    assert 'fee-form-open">' in fees.render_form(link, '2026.11.15.', dt.datetime(2026, 11, 16, 23, 58))
    html = fees.render_form(link, '2026.11.15.', dt.datetime(2026, 11, 16, 23, 59))
    assert '<div class="fee-form-open" hidden>' in html and '<p class="fee-form-closed">' in html
    open_form = fees.render_form('https://docs.google.com/forms/d/e/1/formResponse', '')
    assert 'data-until' not in open_form and 'formResponse' in open_form and 'fee-form-closed' not in open_form
