import datetime as dt

import pytest

import send_reminders as reminders
import sync_common as common
from conftest import csv_text, read_json
from test_sync_programs import HEADER

MEDIA = [('Korzenszky Enikő', 'media@cserkesz.hu', '+36 30 123 4567')]


def row(**values):
    base = {'name': 'Őszi portya', 'start': dt.date(2026, 11, 14), 'end': None, 'start_time': '', 'end_time': '',
            'place': 'Erdő', 'report': '', 'c1_name': 'Kiss Anna', 'c1_email': 'anna@cserkesz.hu',
            'c2_name': '', 'c2_email': '', 'label': '2. sor (Őszi portya)'}
    base.update(values)
    return base


# ---------- times ----------

def test_start_and_end_of():
    assert reminders.start_of(row()) == dt.datetime(2026, 11, 14, 8, 0)          # all-day: 8:00
    assert reminders.end_of(row()) == dt.datetime(2026, 11, 14, 23, 59)
    timed = row(start_time='22:00', end_time='02:00')
    assert reminders.end_of(timed) == dt.datetime(2026, 11, 15, 2, 0)             # overnight
    multi = row(end=dt.date(2026, 11, 16), start_time='09:00', end_time='08:00')
    assert reminders.end_of(multi) == dt.datetime(2026, 11, 16, 8, 0)             # explicit end date
    assert reminders.end_of(row(end_time='12:00')) == dt.datetime(2026, 11, 14, 12, 0)


@pytest.mark.parametrize('now, sent, report, expected', [
    ('2026-11-13 07:59', {}, '', None),                    # more than 24 h before: not yet
    ('2026-11-13 08:00', {}, '', 'photos'),                # exactly 24 h before
    ('2026-11-14 07:59', {}, '', 'photos'),
    ('2026-11-14 08:00', {}, '', None),                    # started: too late for the photos mail
    ('2026-11-13 09:00', {'photos': 'x', 'photos_organiser': 'x'}, '', None),
    ('2026-11-13 09:00', {'photos': 'x'}, '', 'photos'),   # the organiser's one failed last time
    ('2026-11-15 23:59', {}, '', 'report'),
    ('2026-11-15 23:58', {}, '', None),
    ('2026-11-16 10:00', {}, 'Jó volt', None),             # the report is there
    ('2026-11-21 23:59', {'report': 'x', 'report_organiser': 'x'}, '', 'report_again'),
    ('2026-11-21 23:59', {}, '', 'report_again'),          # a missed first reminder is not sent late
    ('2026-11-25 10:00', {'report_again': 'x'}, '', None),
    ('2026-11-29 00:00', {}, '', None),                    # given up after 14 days
])
def test_due(now, sent, report, expected):
    assert reminders.due(row(report=report), dt.datetime.fromisoformat(now), sent) == expected


# ---------- people and texts ----------

def test_recipients_skip_invalid_and_duplicates():
    people = reminders.recipients(row(c1_email='ANNA@cserkesz.hu', c2_name='Anna 2', c2_email='anna@cserkesz.hu'))
    assert people == [('Kiss Anna', 'ANNA@cserkesz.hu')]
    assert reminders.recipients(row(c1_email='rossz')) == []


def test_media_people(issues):
    text = csv_text([['Név', 'Szerep', 'E-mail (kötelező)', 'Telefon'],
                     ['Korzenszky Enikő', 'médiás', 'media@cserkesz.hu', '36301234567'],
                     ['Névtelen', '', '', ''], ['', '', 'x@x.hu', '']])
    assert reminders.media_people(text) == [('Korzenszky Enikő', 'media@cserkesz.hu', '+36 30 123 4567')]
    assert len(issues()) == 2


def test_person_text():
    assert reminders.person_text(MEDIA, with_phone=True) == 'Korzenszky Enikő (media@cserkesz.hu, +36 30 123 4567)'
    assert reminders.person_text([('', 'a@x.hu'), ('B', 'b@x.hu')]) == 'a@x.hu (a@x.hu) és B (b@x.hu)'


def test_with_article_and_when_text():
    assert reminders.with_article('Őszi portya') == 'az Őszi portya'
    assert reminders.with_article('5 napos túra') == 'az 5 napos túra'
    assert reminders.when_text(row(start_time='09:00', end_time='16:00')) == '2026. november 14., 09:00–16:00, Erdő'
    assert reminders.when_text(row(place='')) == '2026. november 14.'


@pytest.mark.parametrize('stage', ['photos', 'report'])
def test_organiser_mails(stage):
    subject, body = reminders.compose_organiser(stage, row(), reminders.recipients(row()), MEDIA)
    assert body.startswith('Kedves Anna!')
    assert 'a csapat médiásának: Korzenszky Enikő (media@cserkesz.hu, +36 30 123 4567)' in body
    assert 'táblázat' not in body.lower().replace('a táblázat', '') or 'Programos táblázat:' not in body
    assert body.endswith(f'Jó munkát!\n{reminders.SIGNATURE}\n')


def test_media_mails_singular_plural_and_no_organiser():
    two = row(c2_name='Nagy Béla', c2_email='bela@cserkesz.hu')
    _, photos = reminders.compose_media('photos', two, reminders.recipients(two), MEDIA)
    assert 'A program szervezői: Kiss Anna (anna@cserkesz.hu) és Nagy Béla' in photos
    assert 'kérj tőlük' in photos and 'készítsenek' in photos and 'küldjék' in photos
    _, one = reminders.compose_media('photos', row(), reminders.recipients(row()), MEDIA)
    assert 'kérj tőle' in one and 'készítsen képeket' in one and 'küldje el' in one
    _, none = reminders.compose_media('report', row(c1_name='', c1_email=''), [], MEDIA)
    assert 'nincs megadva szervező' in none and 'kérd el a szervezőktől a beszámolót és a képeket.' in none
    subject, again = reminders.compose_media('report_again', row(), reminders.recipients(row()), MEDIA)
    assert subject == 'Emlékeztető: még hiányzik az Őszi portya beszámolója'
    assert again.startswith('Kedves Enikő!') and 'keresd meg a szervezőt' in again


def test_media_mails_contain_links(monkeypatch):
    monkeypatch.setattr(reminders, 'LINKS', 'Programos táblázat: L1\nProgram képek mappa: L2')
    _, body = reminders.compose_media('photos', row(), reminders.recipients(row()), MEDIA)
    assert 'Programos táblázat: L1\nProgram képek mappa: L2\n\nJó munkát!' in body


def test_messages_skip_organiser_without_address():
    keys = [m[0] for m in reminders.messages('photos', row(c1_email=''), MEDIA)]
    assert keys == ['photos']
    assert [m[0] for m in reminders.messages('report_again', row(), MEDIA)] == ['report_again']


# ---------- state ----------

def test_load_state_migrates_organiser_mails_before_the_media_person(tmp_path, monkeypatch):
    path = tmp_path / 'r.json'
    path.write_text('{"a": {"photos": "2026-10-25T14:23", "end": "2026-10-30"},'
                    ' "b": {"report": "2026-11-01T10:00"}}', encoding='utf-8')
    monkeypatch.setattr(reminders, 'STATE', str(path))
    state = reminders.load_state()
    assert state['a']['photos_organiser'] == '2026-10-25T14:23'
    assert 'report_organiser' not in state['b']


# ---------- whole runs ----------

class FakeMailer:
    enabled = True

    def __init__(self, fail_for=()):
        self.sent, self.fail_for = [], fail_for

    def deliver(self, to, subject, body, label, on_auth_error=None):
        if any(address in self.fail_for for _, address in to):
            return False
        self.sent.append((to, subject))
        return True


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / 'reminders.json'
    monkeypatch.setattr(reminders, 'STATE', str(path))
    return path


def test_run_sends_records_and_retries_only_the_failed(state_file):
    rows = [row()]
    now = dt.datetime(2026, 11, 13, 20, 0)
    mailer = FakeMailer(fail_for=('media@cserkesz.hu',))
    reminders.run(rows, now, mailer, MEDIA)
    assert [s for _, s in mailer.sent] == ['Hamarosan kezdődik: Őszi portya – ne felejts el képeket készíteni!']
    state = read_json(state_file)['oszi-portya-20261114']
    assert set(state) == {'photos_organiser', 'end'}
    mailer = FakeMailer()
    reminders.run(rows, now + dt.timedelta(hours=1), mailer, MEDIA)
    assert [to[0][1] for to, _ in mailer.sent] == ['media@cserkesz.hu']
    reminders.run(rows, now + dt.timedelta(hours=2), FakeMailer(), MEDIA)
    assert set(read_json(state_file)['oszi-portya-20261114']) == {'photos', 'photos_organiser', 'end'}


def test_run_forgets_old_programs_and_warns_without_organiser(state_file, issues):
    state_file.write_text('{"regi-20200101": {"end": "2020-01-01", "photos": "x"}}', encoding='utf-8')
    reminders.run([row(c1_email='')], dt.datetime(2026, 11, 15, 23, 59), FakeMailer(), MEDIA)
    assert 'regi-20200101' not in read_json(state_file)
    assert 'a szervező nem kap emlékeztetőt' in issues()[0]['message']


def test_run_without_smtp_does_not_save(state_file, capsys):
    mailer = FakeMailer()
    mailer.enabled = False
    reminders.run([row()], dt.datetime(2026, 11, 13, 20, 0), mailer, MEDIA)
    assert not state_file.exists() and mailer.sent == []
    assert '(SMTP nélkül nem küldöm el)' in capsys.readouterr().out


def test_test_mode(monkeypatch, capsys, issues):
    monkeypatch.setenv('TEST_ORGANISER', 'true')
    monkeypatch.setenv('TEST_ORGANISER_TO', 't@x.hu')
    mailer = FakeMailer()
    rows = [row(name='Régi', start=dt.date(2020, 1, 1)), row()]
    reminders.test(rows, dt.datetime(2026, 11, 1, 10, 0), mailer, [])
    assert [to for to, _ in mailer.sent] == [[('', 't@x.hu')]] * 2             # 2 organiser e-mails
    assert all('Őszi portya' in s for _, s in mailer.sent)                      # the next program
    assert 'helyőrző' in issues()[0]['message']                                 # no media person yet
    monkeypatch.setenv('TEST_MEDIA', 'true')                                     # no address, no media → skipped
    mailer = FakeMailer()
    reminders.test(rows, dt.datetime(2026, 11, 1, 10, 0), mailer, [])
    assert len(mailer.sent) == 2


def test_test_mode_failures(monkeypatch, issues):
    monkeypatch.setenv('TEST_MEDIA', 'true')
    mailer = FakeMailer()
    mailer.enabled = False
    with pytest.raises(SystemExit):
        reminders.test([row()], dt.datetime(2026, 11, 1), mailer, MEDIA)
    with pytest.raises(SystemExit):
        reminders.test([], dt.datetime(2026, 11, 1), FakeMailer(), MEDIA)
    assert 'Nincs program' in issues()[-1]['message']


def test_test_mode_nothing_asked(capsys):
    reminders.test([row()], dt.datetime(2026, 11, 1), FakeMailer(), MEDIA)
    assert 'nem volt kérve' in capsys.readouterr().out


FIXED_NOW = '2026-03-10 10:00'


@pytest.fixture
def main_files(site, tmp_path, monkeypatch, state_file):
    snapshot = tmp_path / 'programs.csv'
    future = '2026.03.11.'   # all-day, so it starts at 8:00: within 24 hours of FIXED_NOW
    line = dict.fromkeys(HEADER, '')
    line.update({'Név': 'Holnapi', 'Kezdő dátum': future, 'Kapcsolattartó 1 neve': 'Kiss Anna',
                 'Kapcsolattartó 1 e-mail (kötelező)': 'anna@cserkesz.hu', 'Helyszín': 'x', 'Leírás': 'y'})
    snapshot.write_text(csv_text([HEADER, [line[h] for h in HEADER]]), encoding='utf-8')
    media = tmp_path / 'media.csv'
    media.write_text(csv_text([['Név', 'E-mail'], ['Korzenszky Enikő', 'media@cserkesz.hu']]), encoding='utf-8')
    return snapshot, media


def test_main_full_run(main_files, smtp, monkeypatch, issues):
    snapshot, media = main_files
    monkeypatch.setattr('sys.argv', ['send_reminders.py', '--file', str(snapshot), '--media-file', str(media),
                                     '--now', FIXED_NOW])
    reminders.main()
    subjects = sorted(m['Subject'] for m in smtp.sent)
    assert len(subjects) == 2 and all('Holnapi' in s for s in subjects)
    assert any('CSPK_WEBOLDAL_ADATOK_LINK' in i['message'] for i in issues())


def test_main_without_media_sends_nothing(main_files, smtp, monkeypatch, tmp_path, issues):
    snapshot, _ = main_files
    empty = tmp_path / 'm.csv'
    empty.write_text(csv_text([['Név', 'E-mail'], ['Valaki', '']]), encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['send_reminders.py', '--file', str(snapshot), '--media-file', str(empty)])
    reminders.main()
    assert smtp.sent == [] and 'Nincs érvényes médiás' in issues()[-1]['message']


def test_main_missing_media_sheet_is_not_a_crash(main_files, smtp, monkeypatch, tmp_path, issues):
    snapshot, _ = main_files
    monkeypatch.setattr('sys.argv', ['send_reminders.py', '--file', str(snapshot)])    # no workbook at all
    reminders.main()
    assert smtp.sent == []


def test_main_test_mode(main_files, smtp, monkeypatch):
    snapshot, media = main_files
    monkeypatch.setenv('TEST_MEDIA', 'true')
    monkeypatch.setattr('sys.argv', ['send_reminders.py', '--file', str(snapshot), '--media-file', str(media),
                                     '--now', '2020-01-01 10:00'])
    reminders.main()
    assert len(smtp.sent) == 3 and all(m['Subject'].startswith('[TESZT – médiásnak]') for m in smtp.sent)
    assert not (common.ROOT and reminders.STATE and __import__('os').path.exists(reminders.STATE))
