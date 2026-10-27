import datetime as dt
import io
import json
import urllib.error

import pytest

import sync_calendar as cal
from conftest import csv_text
from test_sync_programs import HEADER, program


def rows_of(*sheet_rows):
    import sync_programs
    rows, _ = sync_programs.parse_rows(csv_text([HEADER, *sheet_rows]))
    return rows


# ---------- events from the sheet ----------

def test_when_all_day_timed_overnight_and_default_length():
    base = {'start': dt.date(2030, 1, 10), 'end': None, 'start_time': None, 'end_time': None}
    assert cal.when(base) == ({'date': '2030-01-10'}, {'date': '2030-01-11'})
    assert cal.when({**base, 'end': dt.date(2030, 1, 12)}) == ({'date': '2030-01-10'}, {'date': '2030-01-13'})
    start, end = cal.when({**base, 'start_time': '22:00', 'end_time': '02:00'})
    assert (start['dateTime'], end['dateTime']) == ('2030-01-10T22:00:00', '2030-01-11T02:00:00')
    assert start['timeZone'] == 'Europe/Budapest'
    start, end = cal.when({**base, 'start_time': '18:30'})
    assert end['dateTime'] == '2030-01-10T19:30:00'
    start, end = cal.when({**base, 'end': dt.date(2030, 1, 11), 'start_time': '20:00', 'end_time': '01:00'})
    assert end['dateTime'] == '2030-01-11T01:00:00'


def test_description_upcoming_and_past():
    upcoming = rows_of(program(Leírás='Gyertek', **{'Kezdő idő': '17:45', 'Időpont megjegyzése': 'gyülekező',
                                                    'Kapcsolattartó 1 telefon': '06301234567',
                                                    'Facebook-esemény': 'https://fb.me/x'}))[0]
    text = cal.description(upcoming, 'portya-1')
    assert text.split('\n\n') == ['Gyertek', 'Időpont: 17:45 (gyülekező)',
                                  'Kérdés esetén keresd: Kiss Anna (anna@cserkesz.hu, +36 30 123 4567)',
                                  'Facebook-esemény: https://fb.me/x',
                                  f'Részletek a weboldalon: {cal.SITE_URL}programok.html#portya-1']
    past = rows_of(program(Leírás='Gyertek', Beszámoló='Jó volt', **{'Kezdő dátum': '2020.01.01.'}))[0]
    assert cal.description(past, 'x').startswith('Jó volt')


def test_build_events_ids_hash_and_stability():
    rows = rows_of(program(Név='Mise'), program(Név='Mise'))
    first, second = cal.build_events(rows), cal.build_events(rows)
    assert first == second and len(first) == 2
    for event_id, body in first.items():
        assert event_id.startswith('p802') and set(event_id) <= set('0123456789abcdefghijklmnopqrstuv')
        assert body['colorId'] == '10' and body['extendedProperties']['private']['source'] == '802-weboldal'
    changed = cal.build_events(rows_of(program(Név='Mise', Helyszín='Máshol'), program(Név='Mise')))
    hashes = lambda events: [e['extendedProperties']['private']['hash'] for e in events.values()]  # noqa: E731
    assert hashes(changed)[0] != hashes(first)[0] and hashes(changed)[1] == hashes(first)[1]


# ---------- sync against a fake calendar ----------

def http_error(code, message='x'):
    return urllib.error.HTTPError('u', code, 'err', {}, io.BytesIO(json.dumps({'error': {'message': message}}).encode()))


class FakeCalendar:
    def __init__(self, events=None, fail=None):
        self.events = dict(events or {})
        self.fail = fail or {}            # (method, id) → HTTPError
        self.calls = []

    def ours(self):
        return json.loads(json.dumps(self.events))

    def call(self, method, path='', body=None, query=None):
        event_id = path.strip('/') or body['id']
        self.calls.append((method, event_id))
        if (method, event_id) in self.fail:
            raise self.fail.pop((method, event_id))
        if method == 'DELETE':
            self.events[event_id]['status'] = 'cancelled'
        else:
            self.events[event_id] = body
        return {}


def test_sync_add_skip_update_delete_restore():
    wanted = cal.build_events(rows_of(program(Név='A'), program(Név='B')))
    calendar = FakeCalendar()
    assert cal.sync(calendar, wanted) == (2, 0, 0)
    assert cal.sync(calendar, wanted) == (0, 0, 0)
    fewer = cal.build_events(rows_of(program(Név='A', Helyszín='Új')))
    assert cal.sync(calendar, fewer) == (0, 1, 1)
    assert cal.sync(calendar, wanted) == (0, 2, 0)        # A changes back, B comes back from "cancelled"


def test_sync_conflict_uses_update():
    wanted = cal.build_events(rows_of(program(Név='A')))
    event_id = next(iter(wanted))
    calendar = FakeCalendar(fail={('POST', event_id): http_error(409)})
    assert cal.sync(calendar, wanted) == (0, 1, 0)
    assert calendar.calls == [('POST', event_id), ('PUT', event_id)]


def test_sync_write_not_allowed_stops(issues):
    wanted = cal.build_events(rows_of(program(Név='A')))
    calendar = FakeCalendar(fail={('POST', next(iter(wanted))): http_error(403, 'forbidden')})
    with pytest.raises(SystemExit):
        cal.sync(calendar, wanted)
    assert 'nem engedélyezett (HTTP 403: forbidden)' in issues()[0]['message']


def test_sync_other_errors_are_warnings(issues):
    wanted = cal.build_events(rows_of(program(Név='A')))
    event_id = next(iter(wanted))
    old = {'gone': {'id': 'gone', 'summary': 'Régi', 'status': 'confirmed'},
           'twice': {'id': 'twice', 'summary': 'Kétszer', 'status': 'confirmed'}}
    calendar = FakeCalendar(old, fail={('POST', event_id): http_error(400, 'rossz'),
                                       ('DELETE', 'gone'): http_error(500), ('DELETE', 'twice'): http_error(410)})
    assert cal.sync(calendar, wanted) == (0, 0, 0)
    messages = [i['message'] for i in issues()]
    assert any('HTTP 400: rossz' in m for m in messages) and any('Régi: a törlés nem sikerült' in m for m in messages)
    assert not any('Kétszer' in m for m in messages)       # 410 = already deleted, no warning


def test_sync_dry_run(capsys):
    wanted = cal.build_events(rows_of(program(Név='A')))
    calendar = FakeCalendar({'old': {'id': 'old', 'summary': 'Régi', 'status': 'confirmed'}})
    cal.sync(calendar, wanted, dry_run=True)
    out = capsys.readouterr().out
    assert 'Felvenném: A' in out and 'Törölném: Régi' in out and calendar.calls == []


# ---------- the HTTP layer ----------

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def test_calendar_paging_and_requests(monkeypatch):
    pages = [{'items': [{'id': 'a'}], 'nextPageToken': 'T'}, {'items': [{'id': 'b'}]}]
    seen = []

    def opener(request, timeout):
        seen.append((request.get_method(), request.full_url, request.headers.get('Authorization')))
        return FakeResponse(json.dumps(pages.pop(0)).encode())
    monkeypatch.setattr(cal.urllib.request, 'urlopen', opener)
    calendar = cal.Calendar('TOKEN', 'abc@group.calendar.google.com')
    assert set(calendar.ours()) == {'a', 'b'}
    assert 'abc%40group.calendar.google.com/events?privateExtendedProperty=source%3D802-weboldal' in seen[0][1]
    assert 'pageToken=T' in seen[1][1] and seen[0][2] == 'Bearer TOKEN'
    monkeypatch.setattr(cal.urllib.request, 'urlopen', lambda request, timeout: FakeResponse(b''))
    assert calendar.call('DELETE', '/x') == {}


def test_access_token_signs_a_jwt(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives import hashes
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    sent = {}

    def opener(request, timeout):
        sent['data'] = request.data.decode()
        return FakeResponse(b'{"access_token": "ya29"}')
    monkeypatch.setattr(cal.urllib.request, 'urlopen', opener)
    token = cal.access_token({'client_email': 'robot@x.iam.gserviceaccount.com', 'private_key': pem,
                              'token_uri': 'https://oauth2.googleapis.com/token'})
    assert token == 'ya29'
    import base64
    import urllib.parse
    assertion = urllib.parse.parse_qs(sent['data'])['assertion'][0]
    header, claims, signature = assertion.split('.')
    pad = lambda s: s + '=' * (-len(s) % 4)  # noqa: E731
    claims = json.loads(base64.urlsafe_b64decode(pad(claims)))
    assert claims['iss'] == 'robot@x.iam.gserviceaccount.com' and claims['scope'] == cal.SCOPE
    assert json.loads(base64.urlsafe_b64decode(pad(header))) == {'alg': 'RS256', 'typ': 'JWT'}
    key.public_key().verify(base64.urlsafe_b64decode(pad(signature)), assertion.rsplit('.', 1)[0].encode(),
                            padding.PKCS1v15(), hashes.SHA256())     # raises if the signature is wrong


def test_access_token_errors(monkeypatch, issues):
    with pytest.raises(SystemExit):
        cal.access_token({'client_email': 'r@x', 'private_key': 'nem kulcs', 'token_uri': 'https://t'})
    assert 'kulcs sérült' in issues()[-1]['message']
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()

    def denied(request, timeout):
        raise urllib.error.HTTPError('u', 400, 'bad', {}, io.BytesIO(b'{}'))
    monkeypatch.setattr(cal.urllib.request, 'urlopen', denied)
    with pytest.raises(SystemExit):
        cal.access_token({'client_email': 'r@x', 'private_key': pem, 'token_uri': 'https://t'})
    assert 'bejelentkezése nem sikerült (HTTP 400)' in issues()[-1]['message']


def test_http_error_text_without_json():
    assert cal.http_error_text(urllib.error.HTTPError('u', 500, 'x', {}, io.BytesIO(b'<html>'))) == ''


# ---------- main ----------

@pytest.fixture
def snapshot(tmp_path):
    path = tmp_path / 'p.csv'
    path.write_text(csv_text([HEADER, program(Név='A')]), encoding='utf-8')
    return path


def run_main(monkeypatch, path, *extra):
    monkeypatch.setattr('sys.argv', ['sync_calendar.py', '--file', str(path), *extra])
    cal.main()


def test_main_show(monkeypatch, snapshot, capsys):
    run_main(monkeypatch, snapshot, '--show')
    assert json.loads(capsys.readouterr().out)['summary'] == 'A'


def test_main_without_key_is_a_warning(monkeypatch, snapshot, issues):
    run_main(monkeypatch, snapshot)
    assert 'GOOGLE_SERVICE_ACCOUNT_KEY' in issues()[0]['message']


@pytest.mark.parametrize('key, message', [
    ('nem json', 'nem a robotfiók JSON kulcsfájlja'),
    ('{"client_email": "x"}', 'nem a robotfiók JSON kulcsfájlja'),
    ('[1, 2]', 'nem a robotfiók JSON kulcsfájlja'),
])
def test_main_bad_key(monkeypatch, snapshot, issues, key, message):
    monkeypatch.setenv('GOOGLE_SERVICE_ACCOUNT_KEY', key)
    monkeypatch.setenv('PROGRAM_CALENDAR_ID', 'c@group.calendar.google.com')
    with pytest.raises(SystemExit):
        run_main(monkeypatch, snapshot)
    assert message in issues()[-1]['message']


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv('GOOGLE_SERVICE_ACCOUNT_KEY', '{"client_email": "r@x", "private_key": "k"}')
    monkeypatch.setenv('PROGRAM_CALENDAR_ID', 'c@group.calendar.google.com')
    monkeypatch.setattr(cal, 'access_token', lambda key: 'TOKEN')


def test_main_empty_sheet_does_not_empty_the_calendar(monkeypatch, tmp_path, keyed, issues):
    path = tmp_path / 'e.csv'
    path.write_text(csv_text([HEADER, program(Megjelenjen='nem')]), encoding='utf-8')
    with pytest.raises(SystemExit):
        run_main(monkeypatch, path)
    assert 'nem ürítem ki a naptárat' in issues()[-1]['message']


def test_main_success(monkeypatch, snapshot, keyed, capsys):
    fake = FakeCalendar()
    monkeypatch.setattr(cal, 'Calendar', lambda token, calendar_id: fake)
    run_main(monkeypatch, snapshot)
    assert 'Google Naptár: 1 program; új: 1, frissített: 0, törölt: 0.' in capsys.readouterr().out


@pytest.mark.parametrize('error, message', [
    (http_error(404, 'Not Found'), 'Jó a PROGRAM_CALENDAR_ID'),
    (http_error(503), 'nem válaszolt rendesen (HTTP 503)'),
    (urllib.error.URLError('nincs hálózat'), 'nem érhető el (nincs hálózat)'),
])
def test_main_api_errors(monkeypatch, snapshot, keyed, issues, error, message):
    class Broken(FakeCalendar):
        def ours(self):
            raise error
    monkeypatch.setattr(cal, 'Calendar', lambda token, calendar_id: Broken())
    with pytest.raises(SystemExit):
        run_main(monkeypatch, snapshot)
    assert message in issues()[-1]['message']
