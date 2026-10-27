"""E-mail helpers shared by the reminder and report scripts.

  - Mailer: SMTP sending from the admin account (ADMIN_EMAIL / ADMIN_JELSZO, a Google app password),
    with one connection per run and the same error handling everywhere (deliver);
  - test e-mails: the Run workflow form has a checkbox and an address per e-mail kind
    (TEST_<KIND>, TEST_<KIND>_TO) and "Csak a tesztlevelek" (ONLY_TESTS);
  - periodic_reminder: the common flow of the seasonal reminders (troops, camps);
  - small Hungarian text helpers (given name, "X és Y" lists).
"""
import contextlib
import datetime as dt
import email.message
import email.utils
import os
import smtplib
import ssl

import sync_common as common

SENDER_NAME = '802. sz. Szent Korona Cserkészcsapat'
SIGNATURE = '802. sz. Szent Korona Cserkészcsapat'
TEST_KINDS = ('ORGANISER', 'MEDIA', 'TROOP', 'CAMP')


# ---------- Hungarian text ----------

def given_name(full_name):
    """Hungarian name order: family name first, so "Pálinkás Péter" → "Péter"."""
    words = [w for w in full_name.split() if w.lower().rstrip('.') not in ('dr', 'ifj', 'id')]
    return words[1] if len(words) > 1 else (words[0] if words else '')


def join_and(parts):
    """["a", "b", "c"] → "a, b és c"."""
    parts = list(parts)
    return ' és '.join([', '.join(parts[:-1]), parts[-1]]) if len(parts) > 1 else (parts[0] if parts else '')


def greeting(names, fallback='Sziasztok!'):
    """"Kedves Anna és Béla!" from full names; the fallback greeting without any."""
    given = [given_name(name) for name in names if given_name(name)]
    return f'Kedves {join_and(given)}!' if given else fallback


# ---------- sending ----------

class Mailer:
    """SMTP sender of the admin account; use it as a context manager (closes the connection)."""

    def __init__(self):
        self.user = os.environ.get('ADMIN_EMAIL', '').strip()
        self.password = os.environ.get('ADMIN_JELSZO', '').replace(' ', '')
        self.host = os.environ.get('SMTP_HOST', '').strip() or 'smtp.gmail.com'
        self.port = int(os.environ.get('SMTP_PORT', '').strip() or 465)
        self.enabled = bool(self.user and self.password)
        self.server = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def send(self, to, subject, body):
        """Sends one e-mail; to = [(name, address)]. Raises the SMTP / network errors."""
        message = email.message.EmailMessage()
        message['From'] = email.utils.formataddr((SENDER_NAME, self.user))
        message['To'] = ', '.join(email.utils.formataddr(person) for person in to)
        message['Subject'] = ' '.join(subject.split())   # no line breaks in a header
        message['Date'] = email.utils.formatdate(localtime=True)
        message['Message-ID'] = email.utils.make_msgid(domain=self.user.split('@')[-1])
        message.set_content(body)
        if self.server is None:
            self.server = smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=30)
            self.server.login(self.user, self.password)
        self.server.send_message(message)

    def deliver(self, to, subject, body, label, on_auth_error=None):
        """Sends with the usual error handling: True if sent. A failed sign-in stops the script (after
        on_auth_error, e.g. saving what was sent before); any other error is a warning, and the next run
        tries again."""
        try:
            self.send(to, subject, body)
            return True
        except smtplib.SMTPAuthenticationError:
            if on_auth_error:
                on_auth_error()
            common.fail('Az SMTP bejelentkezés nem sikerült: ellenőrizd az ADMIN_EMAIL és ADMIN_JELSZO titkot '
                        '(Google-fióknál alkalmazásjelszó kell).')
        except (smtplib.SMTPException, OSError) as error:
            common.warn(f'{label}: a levél nem ment el ({type(error).__name__}: {error}); a következő futáskor '
                        'újrapróbálom.')
            self.close()
            return False

    def close(self):
        if self.server is not None:
            with contextlib.suppress(Exception):
                self.server.quit()
            self.server = None


# ---------- test e-mails ----------

def _ticked(name):
    return os.environ.get(name, '').strip().lower() in ('true', '1')


def test_target(kind):
    """None if the test of this kind was not asked for, otherwise the test address ('' = the real
    recipients)."""
    if not _ticked(f'TEST_{kind}'):
        return None
    address = os.environ.get(f'TEST_{kind}_TO', '').strip()
    if address and not common.EMAIL.fullmatch(address):
        common.fail(f'A teszt e-mail cím nem érvényes: "{address}".')
    return address


def testing():
    """True if any test e-mail was asked for, or "Csak a tesztlevelek" is ticked: then the scripts only
    send the tests (a test-only run does not save the state, so a real reminder would go out twice)."""
    return _ticked('ONLY_TESTS') or any(_ticked(f'TEST_{kind}') for kind in TEST_KINDS)


def test_mail(target, real, subject, body, who):
    """(recipients, subject, body) of a test e-mail: to the test address, or to the real recipients."""
    names = ', '.join(f'{name} ({address})' if name else address for name, address in real)
    note = f'[Tesztlevél. Élesben ezt kapná: {names}.]\n\n'
    return ([('', target)] if target else real), f'[TESZT – {who}] {subject}', note + body


# ---------- seasonal reminders ----------

def periodic_reminder(kind, label, state_path, due_key, build):
    """The shared flow of a reminder sent on given days of the year (troop leaders, camp cards).

    due_key(state) → the key of the occasion due now ("2026-09-15"), or None;
    build(test) → (recipients, subject, body), or None when nothing is missing (with test=True it
    must always return an e-mail). Each occasion is handled once (recorded in state_path); the test
    from the Run workflow form ignores the date and records nothing."""
    test_to = test_target(kind)
    if test_to is None and testing():
        print(f'{label}: tesztlevél nem volt kérve (tesztfuttatás, rendes levél sem megy ki).')
        return
    state = common.load_json(state_path, {})
    key = due_key(state)
    if key is None and test_to is None:
        print(f'{label}: ma nincs esedékes levél.')
        return
    mail = build(test_to is not None)
    if mail is None:
        print(f'{label}: minden adat megvan, nem kell levelet küldeni.')
        common.save_json(state_path, {**state, key: 'nem kellett'})
        return
    to, subject, body = mail
    if test_to is not None:
        to, subject, body = test_mail(test_to, to, subject, body, label.lower())
    with Mailer() as mailer:
        if not mailer.enabled:
            print(f'(SMTP nélkül nem küldöm el) {", ".join(a for _, a in to)}: {subject}\n\n{body}')
            return
        if not mailer.deliver(to, subject, body, label):
            return
    print(f'{"Tesztlevél e" if test_to is not None else "E"}lküldve: {", ".join(a for _, a in to)}: {subject}')
    if test_to is None:
        common.save_json(state_path, {**state, key: dt.datetime.now().isoformat(timespec='minutes')})
