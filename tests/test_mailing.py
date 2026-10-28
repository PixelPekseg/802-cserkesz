import smtplib

import pytest

import mailing
import sync_common as common


@pytest.mark.parametrize('name, given', [
    ('Pálinkás Péter', 'Péter'), ('Dr. Kiss Anna', 'Anna'), ('ifj. Nagy Béla Gábor', 'Béla'),
    ('Enikő', 'Enikő'), ('', ''), ('  ', ''),
])
def test_given_name(name, given):
    assert mailing.given_name(name) == given


@pytest.mark.parametrize('parts, text', [
    ([], ''), (['a'], 'a'), (['a', 'b'], 'a és b'), (['a', 'b', 'c'], 'a, b és c'), (iter(['x', 'y']), 'x és y'),
])
def test_join_and(parts, text):
    assert mailing.join_and(parts) == text


def test_greeting():
    assert mailing.greeting(['Kiss Anna', 'Nagy Béla']) == 'Kedves Anna és Béla!'
    assert mailing.greeting(['', '  ']) == 'Sziasztok!'
    assert mailing.greeting([], 'Kedves Médiás!') == 'Kedves Médiás!'


# ---------- Mailer ----------

def test_mailer_disabled_without_credentials():
    assert not mailing.Mailer().enabled


def test_mailer_sends_one_connection_and_clean_headers(smtp):
    with mailing.Mailer() as mailer:
        assert mailer.enabled and mailer.password == 'abcdefgh'      # spaces of the app password removed
        mailer.send([('Kiss\nAnna', 'anna@x.hu'), ('', 'b@x.hu')], 'Tárgy\r\nBcc: evil@x.hu', 'Szöveg')
        mailer.send([('', 'c@x.hu')], 'Második', 'x')
    first = smtp.sent[0]
    assert first['Subject'] == 'Tárgy Bcc: evil@x.hu'          # no header injection
    assert first['To'] == 'Kiss Anna <anna@x.hu>, b@x.hu'
    assert first['From'] == f'"{mailing.SENDER_NAME}" <admin@cserkesz.hu>'   # quoted: it has dots
    assert first.get_content().strip() == 'Szöveg'
    assert len(smtp.sent) == 2 and mailer.server is None          # closed by the context manager


def test_deliver_auth_error_stops_after_callback(smtp, issues):
    smtp.fail_login = True
    saved = []
    with pytest.raises(SystemExit):
        mailing.Mailer().deliver([('', 'a@x.hu')], 'T', 'B', 'X', on_auth_error=lambda: saved.append(1))
    assert saved == [1]
    assert 'Az SMTP bejelentkezés nem sikerült' in issues()[0]['message']


def test_deliver_other_error_is_a_warning_and_reconnects(smtp, issues):
    mailer = mailing.Mailer()
    smtp.fail_send = smtplib.SMTPRecipientsRefused({'a@x.hu': (550, b'nincs')})
    assert mailer.deliver([('', 'a@x.hu')], 'T', 'B', 'Program X') is False
    assert mailer.server is None
    assert issues()[0]['message'].startswith('Program X: a levél nem ment el (küldéskor: SMTPRecipientsRefused')
    smtp.fail_send = None
    assert mailer.deliver([('', 'a@x.hu')], 'T', 'B', 'Program X') is True


def test_dropped_connection_is_retried_once(smtp, issues, monkeypatch):
    drops = [smtplib.SMTPServerDisconnected('Connection unexpectedly closed')]
    original = smtp.send_message

    def flaky(self, message):
        if drops:
            raise drops.pop()
        original(self, message)
    monkeypatch.setattr(smtp, 'send_message', flaky)
    assert mailing.Mailer().deliver([('', 'a@x.hu')], 'T', 'B', 'X') is True
    assert len(smtp.sent) == 1 and issues() == []


def test_dropped_connection_twice_names_the_stage(smtp, issues, monkeypatch):
    def drop(self, user, password):
        raise smtplib.SMTPServerDisconnected('Connection unexpectedly closed')
    monkeypatch.setattr(smtp, 'login', drop)
    mailer = mailing.Mailer()
    assert mailer.deliver([('', 'a@x.hu')], 'T', 'B', 'X') is False
    assert mailer.server is None
    assert issues()[0]['message'].startswith('X: a levél nem ment el (bejelentkezéskor: SMTPServerDisconnected')


def test_password_whitespace_and_line_breaks_are_ignored(smtp, monkeypatch):
    monkeypatch.setenv('ADMIN_JELSZO', 'abcd efgh\nijkl mnop\n')
    assert mailing.Mailer().password == 'abcdefghijklmnop'


def test_close_ignores_errors(smtp):
    mailer = mailing.Mailer()
    mailer.send([('', 'a@x.hu')], 'T', 'B')

    def broken():
        raise OSError('már bontva')
    mailer.server.quit = broken
    mailer.close()
    assert mailer.server is None


# ---------- tests from the test-emails.yml form ----------

def test_test_target(monkeypatch, issues):
    assert mailing.test_target('CAMP') is None
    monkeypatch.setenv('TEST_CAMP', 'false')
    assert mailing.test_target('CAMP') is None
    monkeypatch.setenv('TEST_CAMP', 'True')
    assert mailing.test_target('CAMP') == ''
    monkeypatch.setenv('TEST_CAMP_TO', '  teszt@x.hu ')
    assert mailing.test_target('CAMP') == 'teszt@x.hu'
    monkeypatch.setenv('TEST_CAMP_TO', 'rossz cím')
    with pytest.raises(SystemExit):
        mailing.test_target('CAMP')
    assert 'nem érvényes: "rossz cím"' in issues()[0]['message']


def test_testing_does_not_validate_addresses(monkeypatch):
    assert not mailing.testing()
    monkeypatch.setenv('TEST_TROOP', 'true')
    monkeypatch.setenv('TEST_TROOP_TO', 'rossz')
    assert mailing.testing()          # another kind's broken address must not stop this step
    monkeypatch.delenv('TEST_TROOP')
    monkeypatch.setenv('ONLY_TESTS', '1')
    assert mailing.testing()


def test_test_mail():
    real = [('Kiss Anna', 'a@x.hu'), ('', 'b@x.hu')]
    to, subject, body = mailing.test_mail('t@x.hu', real, 'Tárgy', 'Szöveg', 'médiásnak')
    assert to == [('', 't@x.hu')] and subject == '[TESZT – médiásnak] Tárgy'
    assert body == '[Tesztlevél. Élesben ezt kapná: Kiss Anna (a@x.hu), b@x.hu.]\n\nSzöveg'
    assert mailing.test_mail('', real, 'T', 'B', 'x')[0] == real


# ---------- periodic_reminder ----------

@pytest.fixture
def state(tmp_path):
    return tmp_path / 'state.json'


def build_mail(test):
    return [('Csapat', 'csapat@x.hu')], 'Tárgy', 'Szöveg'


def test_periodic_not_due(state, capsys):
    mailing.periodic_reminder('CAMP', 'Tábori', str(state), lambda s: None, build_mail)
    assert 'ma nincs esedékes levél' in capsys.readouterr().out and not state.exists()


def test_periodic_nothing_missing_is_recorded(state, capsys):
    mailing.periodic_reminder('CAMP', 'Tábori', str(state), lambda s: '2027-03', lambda test: None)
    assert common.load_json(str(state), {}) == {'2027-03': 'nem kellett'}


def test_periodic_sends_once_and_records(state, smtp):
    for _ in range(2):
        mailing.periodic_reminder('CAMP', 'Tábori', str(state),
                                  lambda s: None if '2027-03' in s else '2027-03', build_mail)
    assert len(smtp.sent) == 1
    assert '2027-03' in common.load_json(str(state), {})


def test_periodic_without_smtp_prints_and_does_not_record(state, capsys):
    mailing.periodic_reminder('CAMP', 'Tábori', str(state), lambda s: '2027-03', build_mail)
    assert '(SMTP nélkül nem küldöm el) csapat@x.hu: Tárgy' in capsys.readouterr().out
    assert not state.exists()


def test_periodic_failed_send_is_not_recorded(state, smtp, issues):
    smtp.fail_send = OSError('hálózat')
    mailing.periodic_reminder('CAMP', 'Tábori', str(state), lambda s: '2027-03', build_mail)
    assert not state.exists() and 'Tábori: a levél nem ment el' in issues()[0]['message']


def test_periodic_test_ignores_date_and_records_nothing(state, smtp, monkeypatch):
    monkeypatch.setenv('TEST_CAMP', 'true')
    monkeypatch.setenv('TEST_CAMP_TO', 'teszt@x.hu')
    seen = []
    mailing.periodic_reminder('CAMP', 'Tábori', str(state), lambda s: None,
                              lambda test: seen.append(test) or build_mail(test))
    assert seen == [True] and not state.exists()
    assert smtp.sent[0]['To'] == 'teszt@x.hu' and smtp.sent[0]['Subject'] == '[TESZT – tábori] Tárgy'


def test_periodic_test_of_another_kind_sends_nothing(state, smtp, monkeypatch, capsys):
    monkeypatch.setenv('TEST_TROOP', 'true')
    mailing.periodic_reminder('CAMP', 'Tábori', str(state), lambda s: '2027-03', build_mail)
    assert smtp.sent == [] and 'tesztlevél nem volt kérve' in capsys.readouterr().out
