"""Edge cases found by reading the whole code once more (and the bugs fixed then)."""
import argparse
import datetime as dt
import json
import sys

import pytest

import camp_reminder
import check_site
import mailing
import program_images
import send_reminders as reminders
import sync_calendar as cal
import sync_common as common
import sync_fees as fees
import sync_notices
import sync_programs as programs
import troop_reminder
from conftest import csv_text, xlsx_bytes
from test_seasonal_reminders import CAMP_HEADER, TROOP_HEADER, camp, troop
from test_sync_programs import HEADER, program


# ---------- sync_common ----------

@pytest.mark.parametrize('value, text', [
    (dt.datetime(1899, 12, 30, 17, 45), '17:45'),                 # a time-only cell of Excel
    (dt.datetime(2026, 11, 8, 17, 45), '2026.11.08. 17:45'),      # date and time in one cell
    (dt.datetime(2026, 11, 8), '2026.11.08.'),
    (dt.time(9, 5), '09:05'), (dt.date(2026, 1, 2), '2026.01.02.'),
    (3.0, '3'), (2.5, '2.5'), (0, '0'), (True, 'True'), (None, ''),
])
def test_cell_csv(value, text):
    assert common._cell_csv(value) == text


def test_sheet_error_warning_names_the_real_header_column(capsys):
    text = csv_text([['Lista'], ['Név', 'E-mail', 'Megjelenjen?'], ['Anna', '#REF!', 'igen']])
    rows = common.read_table(text, {'name': 'név', 'email': 'e-mail', 'visible': 'megjelenjen'}, ['name'])
    assert rows[0][1]['email'] == ''
    assert '3. sor, "E-mail" oszlop' in capsys.readouterr().out      # not the title row's (missing) cell


@pytest.mark.parametrize('text, first, warned', [
    ('a@x.hu', 'a@x.hu', False),
    ('  a@x.hu  ', 'a@x.hu', False),
    ('a@x.hu, b@x.hu', 'a@x.hu', True),
    ('a@x.hu;b@x.hu', 'a@x.hu', True),
    ('Kiss Anna <anna@x.hu>', 'anna@x.hu', False),               # a name with the address
    ('(anna@x.hu)', 'anna@x.hu', False),
    ('nem-cim', 'nem-cim', False),                               # no address: returned for the caller's check
    ('', '', False), (None, '', False),
])
def test_first_email(text, first, warned, issues):
    assert common.first_email(text, 'x') == first
    assert bool(issues()) is warned


@pytest.mark.parametrize('word, expected', [
    ('1 napos', 'az'), ('1. raj', 'az'), ('10 napos', 'a'), ('11 fő', 'a'), ('19', 'a'), ('100 fős', 'a'),
    ('199', 'a'), ('1000 Ft', 'az'), ('15000', 'az'), ('100000', 'az'), ('1000000', 'a'), ('5', 'az'),
    ('50', 'az'), ('500', 'az'), ('2', 'a'), ('802@cserkesz.hu', 'a'), ('20', 'a'), ('', 'a'), ('  ', 'a'),
    ('Ünnep', 'az'), ('Ősz', 'az'), ('ápr', 'az'),
])
def test_article_numbers(word, expected):
    assert common.article(word) == expected


@pytest.mark.parametrize('url', [
    'https://www.facebook.com@evil.com/x',            # user info: the real host is evil.com
    'https://evil.com\\@www.facebook.com/',
    'https:///www.facebook.com',
    '//www.facebook.com/x',
    ' javascript://www.facebook.com/%0aalert(1)',
    'https://www.facebook.com/x y',                   # whitespace inside
    'https://www.face\tbook.com/',                    # a tab: the browser drops it
    'https://user:pw@www.facebook.com/',
])
def test_safe_url_tricks(url):
    assert common.safe_url(url, {'www.facebook.com'}) == ''


def test_safe_url_keeps_normal_links():
    assert common.safe_url('  https://www.facebook.com/events/1?ref=x#a  ', {'www.facebook.com'}) == \
        'https://www.facebook.com/events/1?ref=x#a'


def test_parse_date_with_time_and_noise():
    assert common.parse_date('2026.11.30. 14:00') == dt.date(2026, 11, 30)
    assert common.parse_date('kb. 2026. 11. 30-án') == dt.date(2026, 11, 30)
    assert common.parse_date('2026. december 31-ig') == dt.date(2026, 12, 31)


def test_opened_workbook_cache_checks_identity():
    first = xlsx_bytes({'A': [['első']]})
    assert common.xlsx_sheet_as_csv(first, 'A') == 'első'
    second = xlsx_bytes({'A': [['második']]})
    common._OPENED[id(second)] = (first, common._OPENED[id(first)][1])   # a stale entry under the same id
    assert common.xlsx_sheet_as_csv(second, 'A') == 'második'


def test_shared_sheet_with_file_argument_is_none():
    assert common.shared_sheet_csv(argparse.Namespace(file='x.csv', xlsx=None), 'A', common.TEAM_SHEET_ENV) is None


def test_missing_packages_are_reported(monkeypatch, issues):
    monkeypatch.setitem(sys.modules, 'openpyxl', None)        # "import openpyxl" fails
    with pytest.raises(SystemExit):
        common.xlsx_sheet_as_csv(b'x', 'A')
    with pytest.raises(SystemExit):
        fees.load_workbook(b'x')
    monkeypatch.setitem(sys.modules, 'cryptography.hazmat.primitives', None)
    with pytest.raises(SystemExit):
        cal.access_token({'client_email': 'a', 'private_key': 'b', 'token_uri': 'https://t'})
    assert [m['message'].split(' (')[0] for m in issues()] == [
        'Hiányzik az openpyxl csomag', 'Hiányzik az openpyxl csomag', 'Hiányzik a cryptography csomag']


# ---------- programs ----------

def test_bad_end_time_warning_and_card_without_texts(issues):
    rows, _ = programs.parse_rows(csv_text([HEADER, program(Leírás='', **{'Kezdő idő': '10:00', 'Befejező idő': '12h'})]))
    assert rows[0]['end_time'] is None and 'hibás befejező idő ("12h")' in issues()[0]['message']
    html = programs.build_card({**rows[0], 'images': []}, 'x')
    assert 'news-desc' not in html                                # no empty description block


# ---------- reminders ----------

def test_programs_with_the_same_name_and_day_get_separate_records(tmp_path, monkeypatch):
    monkeypatch.setattr(reminders, 'STATE', str(tmp_path / 'r.json'))
    base = {'name': 'Mise', 'start': dt.date(2026, 11, 14), 'end': None, 'start_time': '', 'end_time': '',
            'place': '', 'report': '', 'c2_name': '', 'c2_email': '', 'label': 'x'}
    rows = [{**base, 'start_time': '09:00', 'c1_name': 'A', 'c1_email': 'a@x.hu'},
            {**base, 'start_time': '18:00', 'c1_name': 'B', 'c1_email': 'b@x.hu'}]

    class Mailer:
        enabled, sent = True, []

        def deliver(self, to, subject, body, label, on_auth_error=None):
            self.sent.append(to[0][1])
            return True
    mailer = Mailer()
    reminders.run(rows, dt.datetime(2026, 11, 13, 19, 0), mailer, [('M', 'm@x.hu', '')])
    assert mailer.sent.count('a@x.hu') == 1 and mailer.sent.count('b@x.hu') == 1
    state = json.loads((tmp_path / 'r.json').read_text(encoding='utf-8'))
    assert set(state) == {'mise-20261114', 'mise-20261114-2'}


def test_periodic_test_without_mail_records_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('TEST_CAMP', 'true')
    state = tmp_path / 's.json'
    mailing.periodic_reminder('CAMP', 'Tábori', str(state), lambda s: None, lambda test: None)
    assert not state.exists() and 'nincs miből tesztlevelet írni' in capsys.readouterr().out


def test_seasonal_mains_record_when_nothing_is_missing(tmp_path, monkeypatch, smtp):
    data = tmp_path / 't.csv'
    data.write_text(csv_text([CAMP_HEADER, camp('Jó')]), encoding='utf-8')
    monkeypatch.setattr(camp_reminder, 'STATE', str(tmp_path / 'camp.json'))
    monkeypatch.setattr('sys.argv', ['camp_reminder.py', '--today', '2027-03-01', '--file', str(data)])
    camp_reminder.main()
    troops = tmp_path / 'r.csv'
    troops.write_text(csv_text([TROOP_HEADER, troop('Gomba', '2026', 'Kiss Anna', 'a@x.hu')]), encoding='utf-8')
    monkeypatch.setattr(troop_reminder, 'STATE', str(tmp_path / 'troop.json'))
    monkeypatch.setattr('sys.argv', ['troop_reminder.py', '--today', '2026-09-15', '--file', str(troops)])
    troop_reminder.main()
    assert smtp.sent == []
    assert json.loads((tmp_path / 'camp.json').read_text()) == {'2027-03': 'nem kellett'}
    assert json.loads((tmp_path / 'troop.json').read_text()) == {'2026-09-15': 'nem kellett'}


def test_camp_recipient_without_camp_role(tmp_path, monkeypatch):
    leaders = tmp_path / 'l.csv'
    leaders.write_text(csv_text([['Név', 'Szerep', 'E-mail', 'Megjelenjen?'], ['A', 'Pénzügyek', 'a@x.hu', '']]),
                       encoding='utf-8')
    monkeypatch.setattr(camp_reminder.leaders, 'SNAPSHOT', str(leaders))
    assert camp_reminder.recipient() is None


# ---------- calendar ----------

def test_conflict_then_update_fails_too(issues):
    from test_sync_calendar import FakeCalendar, http_error, rows_of
    wanted = cal.build_events(rows_of(program(Név='A')))
    event_id = next(iter(wanted))
    calendar = FakeCalendar(fail={('POST', event_id): http_error(409), ('PUT', event_id): http_error(400, 'rossz')})
    assert cal.sync(calendar, wanted) == (0, 0, 0)
    assert 'HTTP 400: rossz' in issues()[0]['message']
    calendar = FakeCalendar(fail={('POST', event_id): http_error(409), ('PUT', event_id): http_error(403)})
    with pytest.raises(SystemExit):
        cal.sync(calendar, wanted)


# ---------- fees ----------

def test_fees_blocks_with_header_only_or_empty_rows_and_item_without_title(issues):
    assert fees.read_rows([], 'Díjak', fees.BLOCKS['prices'][1]) == []
    rows = fees.read_rows([['Cím', 'Befizetési határidő', 'Összeg', 'Megjegyzés'], ['', '', '', ''],
                           ['', '2026.04.01.', '15000', '']], 'Részletek', fees.BLOCKS['items'][1])
    assert rows == [{'title': '', 'deadline': '2026.04.01.', 'amount': '15000', 'note': ''}]
    data = {'fields': {**dict.fromkeys(fees.FIELDS, ''), 'from': '2026.01.01.', 'title': 'Tagdíj'},
            'prices': [], 'items': rows, 'costs': []}
    html = fees.render_tab('tagdij', data, dt.date(2026, 6, 1))
    assert '<h3></h3>' in html and 'egy részletnek nincs címe' in issues()[0]['message']


# ---------- notices ----------

def test_notice_with_start_date():
    html = sync_notices.build_notice({'title': 'T', 'message': 'M'}, dt.date(2030, 1, 1), dt.date(2030, 2, 1), None)
    assert 'data-from="2030-01-01" data-until="2030-02-01" hidden' in html


# ---------- images ----------

def test_program_images_without_program_folder(tmp_path, monkeypatch, paths, issues):
    root = tmp_path / 'drive'
    (root / 'Csapatvezetés').mkdir(parents=True)                 # no "Program képek" folder at all
    monkeypatch.setenv('DRIVE_LOCAL_DIR', str(root))
    images = program_images.ProgramImages()
    assert images.images_for('okt_23', 'x') == []
    assert 'nem található a Program képek mappában' in issues()[0]['message']


def test_finish_removes_stray_folders_but_keeps_used_ones(tmp_path, monkeypatch, paths):
    root = tmp_path / 'drive'
    (root / 'Program képek' / 'okt_23').mkdir(parents=True)
    monkeypatch.setenv('DRIVE_LOCAL_DIR', str(root))
    base = paths / 'images' / 'webp' / 'programok'
    (base / 'kezzel-masolt').mkdir(parents=True)                 # not in the state, not used
    (base / 'okt-23').mkdir()
    (base / 'nem-mappa.txt').write_text('x')
    images = program_images.ProgramImages()
    images.images_for('okt_23', 'x')
    images.finish()
    assert not (base / 'kezzel-masolt').exists() and (base / 'nem-mappa.txt').exists()


# ---------- check_site ----------

def test_check_page_reports_a_parser_error(tmp_path, monkeypatch):
    monkeypatch.setattr(check_site, 'ROOT', str(tmp_path))
    page = tmp_path / 'x.html'
    page.write_text('<p>x</p>', encoding='utf-8')

    def broken(self, data):
        raise ValueError('rossz')
    monkeypatch.setattr(check_site.Parser, 'feed', broken)
    assert check_site.check_page(str(page)) == ['x.html: nem olvasható HTML-ként (rossz)']
