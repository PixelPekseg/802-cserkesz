import argparse
import datetime as dt
import ssl
import urllib.error

import pytest

import sync_common as common
from conftest import csv_text, xlsx_bytes


# ---------- dates, phones, text ----------

@pytest.mark.parametrize('text, expected', [
    ('2027.02.03.', dt.date(2027, 2, 3)),
    ('2027-02-03', dt.date(2027, 2, 3)),
    ('2027/2/3', dt.date(2027, 2, 3)),
    ('  2027. 02. 03.  ', dt.date(2027, 2, 3)),
    ('2027. február 3.', dt.date(2027, 2, 3)),
    ('2027. febr. 3.', dt.date(2027, 2, 3)),
    ('2027 Február 3', dt.date(2027, 2, 3)),
    ('2027. márc. 15.', dt.date(2027, 3, 15)),
    ('2027. marcius 15', dt.date(2027, 3, 15)),
    ('2027. apr 1', dt.date(2027, 4, 1)),
    ('2027. jul 1', dt.date(2027, 7, 1)),
    ('2027. szept. 1.', dt.date(2027, 9, 1)),
    ('2028.02.29.', dt.date(2028, 2, 29)),       # leap year
    ('2027.02.29.', None),                         # not a leap year
    ('2026.11.31.', None),                         # November has 30 days
    ('2027.13.01.', None),
    ('2027. hétfő 3.', None),                      # not a month
    ('február 3.', None),                          # no year
    ('', None),
    (None, None),
    ('Hamarosan', None),
])
def test_parse_date(text, expected):
    assert common.parse_date(text) == expected


@pytest.mark.parametrize('raw, expected', [
    ('36707582659', '+36 70 758 2659'),        # the sheet turned "+36 …" into a number
    ('+36302201322', '+36 30 220 1322'),
    ('06302201322', '+36 30 220 1322'),
    ('3612345678', '+36 1 234 5678'),          # Budapest
    ('+3612345678', '+36 1 234 5678'),
    ('0612345678', '+36 1 234 5678'),
    ('+36 30 330 6130', '+36 30 330 6130'),    # already spaced: unchanged
    ('+49 151 1234', '+49 151 1234'),          # foreign: unchanged
    ('  ', '  '),
    ('', ''),
])
def test_fix_phone(raw, expected):
    assert common.fix_phone(raw) == expected


@pytest.mark.parametrize('word, expected', [
    ('Őszi portya', 'az'), ('admin@x.hu', 'az'), ('Úttörő', 'az'), ('1. raj', 'az'), ('5 napos', 'az'),
    ('Cserkészmise', 'a'), ('802@cserkesz.hu', 'a'), ('2. raj', 'a'), ('', 'a'), ('  Erdő', 'az'),
])
def test_article(word, expected):
    assert common.article(word) == expected


@pytest.mark.parametrize('text, fallback, limit, expected', [
    ('Őszi portya', 'x', None, 'oszi-portya'),
    ('  --Árvíztűrő tükörfúrógép!! ', 'x', None, 'arvizturo-tukorfurogep'),
    ('🔥🔥', 'program', None, 'program'),
    ('a' * 50, 'x', 40, 'a' * 40),
    ('abc def ghi', 'x', 4, 'abc'),     # no trailing hyphen after cutting
])
def test_slugify(text, fallback, limit, expected):
    assert common.slugify(text, fallback, limit) == expected


@pytest.mark.parametrize('address, ok', [
    ('nev@cserkesz.hu', True), ('a.b+c@sub.domain.hu', True), ('ANNA@CSERKESZ.HU', True),
    ('nev@cserkesz', False), ('nev cserkesz.hu', False), ('a@b.hu, c@d.hu', False), ('<a@b.hu>', False),
    ('"a"@b.hu', False), ('@b.hu', False), ('', False),
])
def test_email_pattern(address, ok):
    assert bool(common.EMAIL.fullmatch(address)) is ok


@pytest.mark.parametrize('value, hidden', [
    ('nem', True), ('Nem.', True), (' NEM ', True), ('no', True), ('n', True), ('hamis', True), ('0', True),
    ('false', True), ('nem!', True), ('igen', False), ('', False), (None, False), ('nemigen', False),
])
def test_is_hidden(value, hidden):
    assert common.is_hidden(value) is hidden


def test_is_sheet_error():
    assert common.is_sheet_error(' #error! ')
    assert common.is_sheet_error('#N/A')
    assert not common.is_sheet_error('#1 program')


@pytest.mark.parametrize('url, hosts, prefix, expected', [
    ('https://www.facebook.com/x', {'www.facebook.com'}, '', 'https://www.facebook.com/x'),
    ('  https://www.facebook.com/x  ', {'www.facebook.com'}, '', 'https://www.facebook.com/x'),
    ('http://www.facebook.com/x', {'www.facebook.com'}, '', ''),            # not https
    ('https://evil.com/www.facebook.com', {'www.facebook.com'}, '', ''),
    ('https://www.facebook.com.evil.com/', {'www.facebook.com'}, '', ''),
    ('javascript:alert(1)', {'www.facebook.com'}, '', ''),
    ('https://WWW.FACEBOOK.COM/x', {'www.facebook.com'}, '', 'https://WWW.FACEBOOK.COM/x'),
    ('https://docs.google.com/forms/d/x', {'docs.google.com'}, '/forms/', 'https://docs.google.com/forms/d/x'),
    ('https://docs.google.com/document/d/x', {'docs.google.com'}, '/forms/', ''),
])
def test_safe_url(url, hosts, prefix, expected):
    assert common.safe_url(url, hosts, prefix) == expected


def test_contact_lines_escapes_and_links():
    lines = common.contact_lines(" o'brien@x.hu ", '36301234567')
    assert lines[0] == '<a class="inline-link" href="mailto:o&#x27;brien@x.hu">o&#x27;brien@x.hu</a>'
    assert lines[1] == '<a class="inline-link" href="tel:+36301234567">+36 30 123 4567</a>'


@pytest.mark.parametrize('email', ['a@x.hu?cc=evil@y.hu&body=fizess', 'a<b>@x.hu', 'a@x.hu b@y.hu', '"a"@x.hu'])
def test_contact_lines_refuses_mailto_tricks(email, issues):
    assert common.contact_lines(email, '') == []      # no prefilled cc / body, no broken attribute
    assert 'nem tűnik érvényesnek' in issues()[0]['message']


def test_contact_lines_bad_email_and_short_phone(capsys):
    lines = common.contact_lines('nem-email', '112')
    assert lines == ['112']                      # a too short number is text, not a link
    assert 'nem tűnik érvényesnek' in capsys.readouterr().out


# ---------- warnings, errors and the issue list ----------

def test_warn_and_fail_are_recorded(issues, capsys):
    common.warn('első')
    with pytest.raises(SystemExit) as stop:
        common.fail('második')
    assert stop.value.code == 1
    assert [(i['level'], i['message']) for i in issues()] == [('warning', 'első'), ('error', 'második')]
    out = capsys.readouterr().out
    assert 'FIGYELEM: első' in out and 'HIBA: második' in out


def test_quiet_suppresses_warnings_but_not_errors(issues, capsys):
    with common.quiet():
        common.warn('elnyelve')
        with common.quiet():          # nested
            common.warn('ez is')
        common.warn('még mindig csendes')
    common.warn('újra hallható')
    assert [i['message'] for i in issues()] == ['újra hallható']
    assert 'elnyelve' not in capsys.readouterr().out


def test_say_breaks_workflow_commands_in_actions(monkeypatch, capsys):
    common.say('Elküldve: Portya\n::add-mask::x')
    assert capsys.readouterr().out == 'Elküldve: Portya\n::add-mask::x\n'        # locally unchanged
    monkeypatch.setattr(common, 'in_actions', True)
    common.say('Elküldve: Portya\n  ::error::hamis\n::stop-commands::t')
    assert capsys.readouterr().out == 'Elküldve: Portya\n: :error::hamis\n: :stop-commands::t\n'


def test_actions_log_escapes_workflow_commands(monkeypatch, capsys):
    monkeypatch.setattr(common, 'in_actions', True)
    common.warn('sor\n::error::befecskendezve 100%')
    out = capsys.readouterr().out
    assert out.startswith('::warning::sor%0A::error::befecskendezve 100%25')


def test_issue_file_unwritable_does_not_break(monkeypatch, tmp_path):
    monkeypatch.setattr(common, 'ISSUES_FILE', str(tmp_path / 'nincs' / 'ilyen' / 'mappa' / 'x.jsonl'))
    common.warn('nem baj')    # must not raise


# ---------- files ----------

def test_write_atomic_keeps_old_file_on_error(tmp_path, monkeypatch):
    path = tmp_path / 'oldal.html'
    path.write_text('régi', encoding='utf-8')

    def boom(*_):
        raise OSError('lemez megtelt')
    monkeypatch.setattr(common.os, 'replace', boom)
    with pytest.raises(OSError):
        common.write_text(str(path), 'új')
    assert path.read_text(encoding='utf-8') == 'régi'
    assert [p.name for p in tmp_path.iterdir()] == ['oldal.html']    # no temporary file left


def test_json_state_roundtrip_and_broken_file(tmp_path):
    path = tmp_path / 'data' / 'allapot.json'
    assert common.load_json(str(path), {'alap': 1}) == {'alap': 1}
    common.save_json(str(path), {'b': 'ő', 'a': [1]})
    assert path.read_text(encoding='utf-8') == '{\n  "a": [\n    1\n  ],\n  "b": "ő"\n}\n'
    before = path.stat().st_mtime_ns
    common.save_json(str(path), {'a': [1], 'b': 'ő'})    # the same: not rewritten
    assert path.stat().st_mtime_ns == before
    path.write_text('{rossz', encoding='utf-8')
    assert common.load_json(str(path), []) == []


def test_replace_block(tmp_path):
    page = tmp_path / 'p.html'
    page.write_text('<div>\n  <!-- X:START megjegyzés -->\n  régi\n\n  <!-- X:END -->\n</div>\n', encoding='utf-8')
    assert common.replace_block(str(page), 'X', '  új', '  ')
    assert page.read_text(encoding='utf-8') == '<div>\n  <!-- X:START megjegyzés -->\n  új\n\n  <!-- X:END -->\n</div>\n'
    assert not common.replace_block(str(page), 'X', '  új', '  ')    # unchanged
    # a body with regex special characters / backslashes is inserted literally
    assert common.replace_block(str(page), 'X', r'  \1 $& \\n', '  ')
    assert r'\1 $& \\n' in page.read_text(encoding='utf-8')


def test_replace_block_without_markers_fails(tmp_path, issues):
    page = tmp_path / 'p.html'
    page.write_text('<!-- X:START -->\n', encoding='utf-8')
    with pytest.raises(SystemExit):
        common.replace_block(str(page), 'X', 'új', '')
    assert 'X:START / X:END' in issues()[0]['message']


# ---------- reading tables ----------

COLUMNS = {'name': 'név', 'email': 'e-mail', 'photo': ('fotó', 'fájlnév'), 'visible': 'megjelenjen'}


def test_read_table_basic_and_sheet_errors(capsys):
    text = csv_text([['Név', 'E-mail', 'Fájlnév (régi fejléc)', 'Megjelenjen?'],
                     ['Anna', '#ERROR!', 'a.jpg', 'igen'], [], ['', '', '', ''], ['Béla', 'b@x.hu']])
    rows = common.read_table(text, COLUMNS, required=['name', 'visible'])
    assert rows == [(2, {'name': 'Anna', 'email': '', 'photo': 'a.jpg', 'visible': 'igen'}),
                    (5, {'name': 'Béla', 'email': 'b@x.hu', 'photo': '', 'visible': ''})]
    assert 'táblázathiba' in capsys.readouterr().out


def test_read_table_placeholders_are_left_out(issues):
    text = csv_text([['Név', 'E-mail', 'Fájlnév', 'Megjelenjen?'],
                     ['-', 'a@x.hu', '?', 'x'], ['Béla', ' … ', 'b.jpg', '']])
    rows = common.read_table(text, COLUMNS, required=['name', 'visible'])
    assert rows == [(2, {'name': '', 'email': 'a@x.hu', 'photo': '', 'visible': 'x'}),
                    (3, {'name': 'Béla', 'email': '', 'photo': 'b.jpg', 'visible': ''})]
    messages = [issue['message'] for issue in issues()]
    assert len(messages) == 3 and all('helyőrző érték' in m for m in messages)
    assert '2. sor, "Név" oszlop' in messages[0]


@pytest.mark.parametrize('value, placeholder', [
    ('-', True), (' – ', True), ('?', True), ('...', True), ('X', True), ('TBD', True),
    ('', False), (None, False), ('-5', False), ('Sátor', False), ('x db', False),
])
def test_is_placeholder(value, placeholder):
    assert common.is_placeholder(value) is placeholder


def test_read_table_header_lower_down(capsys):
    text = csv_text([['Vezetők listája'], [], ['Név', 'Megjelenjen?'], ['Anna', 'igen']])
    rows = common.read_table(text, COLUMNS, required=['name', 'visible'])
    assert rows == [(4, {'name': 'Anna', 'visible': 'igen'})]
    assert 'a(z) 3. sorban van' in capsys.readouterr().out


def test_read_table_missing_column_fails(issues):
    with pytest.raises(SystemExit):
        common.read_table(csv_text([['Név', 'Valami'], ['Anna', 'x']]), COLUMNS, required=['name', 'visible'])
    assert 'megjelenjen' in issues()[0]['message']


def test_read_table_empty_fails(issues):
    with pytest.raises(SystemExit):
        common.read_table('\n,,\n', COLUMNS, required=['name'])
    assert issues()[0]['message'] == 'A táblázat üres.'


# ---------- workbooks ----------

def test_xlsx_sheet_as_csv_values_and_trailing_rows():
    data = xlsx_bytes({'Programok': [['Név', 'Dátum', 'Idő', 'Szám'],
                                     ['Mise', dt.datetime(2026, 11, 8), dt.time(17, 45), 3.0],
                                     ['Tört', dt.date(2026, 1, 2), None, 2.5],
                                     [None, None], [None]]})
    text = common.xlsx_sheet_as_csv(data, 'programok')     # case-insensitive sheet name
    assert text == 'Név,Dátum,Idő,Szám\nMise,2026.11.08.,17:45,3\nTört,2026.01.02.,,2.5'


def test_xlsx_missing_sheet_and_not_a_workbook(issues):
    with pytest.raises(SystemExit):
        common.xlsx_sheet_as_csv(xlsx_bytes({'A': [['x']]}), 'Programok')
    with pytest.raises(SystemExit):
        common.xlsx_sheet_as_csv(b'<html>nem xlsx</html>', 'Programok')
    messages = [i['message'] for i in issues()]
    assert 'nincs "Programok" lap' in messages[0]
    assert 'nem olvasható Excel-fájlként' in messages[1]


def test_fetch_from_file_xlsx_and_url(tmp_path, monkeypatch, issues):
    local = tmp_path / 'x.csv'
    local.write_bytes('﻿Név\r\nAnna\r\n'.encode('utf-8'))
    assert common.fetch(argparse.Namespace(file=str(local), xlsx=None), 'X') == 'Név\nAnna\n'

    book = tmp_path / 'book.xlsx'
    book.write_bytes(xlsx_bytes({'Rajok': [['Raj neve'], ['Gomba']]}))
    assert common.fetch(argparse.Namespace(file=None, xlsx=str(book)), 'Rajok') == 'Raj neve\nGomba'

    with pytest.raises(SystemExit):
        common.fetch(argparse.Namespace(file=None, xlsx=None), 'Rajok')
    assert 'TEAM_SHEET_URL' in issues()[-1]['message']


def test_workbook_is_downloaded_once_and_shared_between_steps(tmp_path, monkeypatch):
    calls = []
    data = xlsx_bytes({'Rajok': [['Raj neve'], ['Gomba']], 'Táborok': [['Név'], ['Nagytábor']]})
    monkeypatch.setattr(common, 'download', lambda url: calls.append(url) or data)
    monkeypatch.setenv('TEAM_SHEET_URL', 'https://docs.google.com/x')
    monkeypatch.setattr(common, 'CACHE_DIR', str(tmp_path / 'cache'))
    args = argparse.Namespace(file=None, xlsx=None)
    assert common.fetch(args, 'Rajok') == 'Raj neve\nGomba'
    assert common.fetch(args, 'Táborok') == 'Név\nNagytábor'
    common._BOOKS.clear()            # a new step (process): reads the cache on disk
    common._OPENED.clear()
    assert common.fetch(args, 'Táborok') == 'Név\nNagytábor'
    assert calls == ['https://docs.google.com/x']


def test_leaders_sheets_come_from_the_team_workbook_by_default(monkeypatch):
    data = xlsx_bytes({'Programok': [['Név'], ['Toborzó']]})
    monkeypatch.setattr(common, 'download', lambda url: data)
    monkeypatch.setenv('TEAM_SHEET_URL', 'https://docs.google.com/egy')
    args = argparse.Namespace(file=None, xlsx=None)
    assert common.fetch(args, 'Programok', common.LEADERS_SHEET_ENV) == 'Név\nToborzó'


def test_workbook_download_error(monkeypatch, issues):
    def broken(url):
        raise common.DownloadError('HTTP 404')
    monkeypatch.setattr(common, 'download', broken)
    monkeypatch.setenv('LEADERS_SHEET_URL', 'https://docs.google.com/x')
    with pytest.raises(SystemExit):
        common.fetch(argparse.Namespace(file=None, xlsx=None), 'Programok', common.LEADERS_SHEET_ENV)
    assert issues()[0]['message'] == 'A közös táblázat letöltése nem sikerült: HTTP 404'


# ---------- download ----------

class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, limit):
        return self.data[:limit]


def test_download_only_https():
    with pytest.raises(common.DownloadError, match='https'):
        common.download('http://example.com/x')


def test_download_retries_temporary_errors(monkeypatch):
    attempts = []

    def opener(request, timeout):
        attempts.append(1)
        if len(attempts) < 3:
            raise urllib.error.HTTPError(request.full_url, 503, 'busy', {}, None)
        return FakeResponse(b'ok')
    monkeypatch.setattr(common.urllib.request, 'urlopen', opener)
    monkeypatch.setattr(common.time, 'sleep', lambda s: None)
    assert common.download('https://x.hu/a') == b'ok'
    assert len(attempts) == 3


def test_download_permanent_error_and_no_url_in_message(monkeypatch):
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, 'forbidden', {}, None)
    monkeypatch.setattr(common.urllib.request, 'urlopen', opener)
    with pytest.raises(common.DownloadError) as error:
        common.download('https://x.hu/a?key=TITKOS')
    assert str(error.value) == 'HTTP 403' and 'TITKOS' not in str(error.value)


def test_download_gives_up_after_attempts(monkeypatch):
    def opener(request, timeout):
        raise urllib.error.URLError('nincs hálózat')
    monkeypatch.setattr(common.urllib.request, 'urlopen', opener)
    monkeypatch.setattr(common.time, 'sleep', lambda s: None)
    with pytest.raises(common.DownloadError, match='nincs hálózat .3 próbálkozás után.'):
        common.download('https://x.hu/a')


def test_download_ssl_error_is_not_retried(monkeypatch):
    calls = []

    def opener(request, timeout):
        calls.append(1)
        raise urllib.error.URLError(ssl.SSLError('cert'))
    monkeypatch.setattr(common.urllib.request, 'urlopen', opener)
    with pytest.raises(common.DownloadError, match='SSL'):
        common.download('https://x.hu/a')
    assert len(calls) == 1


def test_download_size_limit(monkeypatch):
    monkeypatch.setattr(common.urllib.request, 'urlopen', lambda request, timeout: FakeResponse(b'x' * 3000))
    with pytest.raises(common.DownloadError, match='nagyobb'):
        common.download('https://x.hu/a', max_bytes=2048, attempts=1)


def test_get_args(monkeypatch):
    monkeypatch.setattr('sys.argv', ['x', '--xlsx', 'b.xlsx'])
    args = common.get_args()
    assert args.xlsx == 'b.xlsx' and args.file is None
