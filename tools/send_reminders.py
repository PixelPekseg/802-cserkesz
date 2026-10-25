#!/usr/bin/env python3
"""Reminder e-mails to the contacts of the programs (Programok sheet).

    1. photos:       the program starts within the next 24 hours → "take photos"
    2. report:       1 day after the end, if the Beszámoló column is still empty → "write a report"
    3. report_again: 1 week after the end, if it is still empty → a second reminder

The e-mails go to the contacts' addresses (Kapcsolattartó 1/2 e-mail, required for upcoming
programs, see sync_programs.py), addressed by their given name. Each one is sent only once:
the sent ones are recorded in data/reminders.json (committed by the workflow).

Reads data/programs.csv, the snapshot that sync_programs.py has just saved, so the sheet is not
downloaded twice. Sends through SMTP (Gmail / Google Workspace: an app password):
    SMTP_USER, SMTP_PASSWORD   GitHub Secrets; without them nothing is sent, the would-be e-mails
                               are only listed (and not recorded)
    SMTP_HOST, SMTP_PORT       optional, default smtp.gmail.com:465 (SSL)
    REMINDER_SHEET_LINK        the edit link of the sheet, put into the e-mails (GitHub Secret)
    REMINDER_IMAGES_LINK       the link of the Drive image folder (GitHub Secret)
    REMINDER_TEST_TO           test: sends the three e-mails of the next program only to this
                               address (nothing else is sent, nothing is recorded)

Usage:
    python tools/send_reminders.py
    python tools/send_reminders.py --now "2026-11-07 10:00"   # for testing: a different "now"
    python tools/send_reminders.py --file x.csv               # from a local CSV export
"""
import argparse
import contextlib
import datetime as dt
import email.message
import email.utils
import io
import json
import os
import re
import smtplib
import ssl
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
import sync_programs as programs  # noqa: E402

STATE = os.path.join(common.ROOT, 'data', 'reminders.json')
# The edit link of the sheet and the link of the image folder are GitHub Secrets as well: the
# repository is public, and they may give edit access to whoever has them.
SHEET_LINK = os.environ.get('REMINDER_SHEET_LINK', '').strip()
IMAGES_LINK = os.environ.get('REMINDER_IMAGES_LINK', '').strip()
SENDER_NAME = '802. sz. Szent Korona Cserkészcsapat'
SIGNATURE = '802. sz. Szent Korona Cserkészcsapat'

PHOTOS_AHEAD = dt.timedelta(hours=24)
REPORT_AFTER = dt.timedelta(days=1)
REPORT_AGAIN_AFTER = dt.timedelta(days=7)
# a program that ended longer ago gets no e-mail any more (e.g. old rows when the feature starts)
GIVE_UP_AFTER = dt.timedelta(days=14)
DEFAULT_START = dt.time(8, 0)     # an all-day program counts as starting at 8:00
KEEP_STATE = dt.timedelta(days=60)

warn = common.warn


def given_name(full_name):
    """Hungarian name order: family name first, so "Pálinkás Péter" → "Péter"."""
    words = [w for w in full_name.split() if w.lower().rstrip('.') not in ('dr', 'ifj', 'id')]
    return words[1] if len(words) > 1 else (words[0] if words else '')


def start_of(row):
    time = dt.time.fromisoformat(row['start_time']) if row['start_time'] else DEFAULT_START
    return dt.datetime.combine(row['start'], time)


def end_of(row):
    day = row['end'] or row['start']
    if not row['end_time']:
        return dt.datetime.combine(day, dt.time(23, 59))
    end = dt.datetime.combine(day, dt.time.fromisoformat(row['end_time']))
    if row['start_time'] and end <= start_of(row):
        end += dt.timedelta(days=1)   # overnight, e.g. 22:00–02:00
    return end


def key_of(row):
    return f"{programs.slugify(row['name'])}-{row['start']:%Y%m%d}"


def recipients(row):
    """[(name, address)] of the contacts with a valid e-mail address (no duplicates)."""
    result = []
    for number in ('1', '2'):
        name, address = row[f'c{number}_name'], row[f'c{number}_email']
        if address and programs.EMAIL.fullmatch(address) and address.lower() not in [a.lower() for _, a in result]:
            result.append((name, address))
    return result


def greeting(people):
    names = [given_name(name) for name, _ in people if given_name(name)]
    if not names:
        return 'Kedves Kapcsolattartó!'
    return 'Kedves ' + (' és '.join([', '.join(names[:-1]), names[-1]]) if len(names) > 1 else names[0]) + '!'


def when_text(row):
    parts = [programs.display_date(row['start'], row['end'])]
    if row['start_time']:
        parts.append(row['start_time'] + (f'–{row["end_time"]}' if row['end_time'] else ''))
    if row['place']:
        parts.append(row['place'])
    return ', '.join(parts)


LINKS = '\n'.join(line for line in (f'Programos táblázat: {SHEET_LINK}' if SHEET_LINK else '',
                                    f'Program képek mappa: {IMAGES_LINK}' if IMAGES_LINK else '') if line)
NO_REPLY = 'Ez egy automatikus üzenet, kérlek, ne válaszolj rá! Ha kérdésed van, keresd a csapatparancsnokot!'


def with_article(name):
    """The name with its Hungarian definite article: "az Őszi portya", "a Cserkészmise"."""
    first = name.strip()[:1].lower()
    vowel = first in 'aáeéiíoóöőuúüű' or first in '15'   # "1" (egy) and "5" (öt) are read with a vowel
    return f"{'az' if vowel else 'a'} {name}"


def compose(kind, row, people):
    """(subject, body) of the e-mail."""
    name, date = row['name'], programs.display_date(row['start'], row['end'])
    the_name = with_article(name)
    hello = greeting(people)
    if kind == 'photos':
        subject = f'Hamarosan kezdődik: {name} – ne felejtsetek el képeket készíteni!'
        text = (f'Hamarosan kezdődik {the_name} ({when_text(row)}), melyhez te vagy feltüntetve szervezőként.\n\n'
                'Kérünk, hogy készíts (vagy kérj meg valakit, hogy készítsen) néhány képet a programról, amit '
                'aztán feltehetünk a weboldalra.\n'
                'A képeknek készíts egy almappát a „Program képek” mappába, és töltsd fel őket oda, majd a mappa '
                'nevét írd be a programos táblázat „Képek” oszlopába.\n'
                'Szintén kérünk, hogy a program után írj egy rövid beszámolót arról, ami kikerülhet a weboldalra. '
                'Ezt a programos táblázat „Beszámoló” oszlopába tedd.')
    elif kind == 'report':
        subject = f'Hogy sikerült {the_name}? Írj róla beszámolót!'
        text = (f'Reméljük, jól sikerült {the_name} ({date})! Kérünk, írj róla néhány mondatos beszámolót a '
                'programos táblázat „Beszámoló” oszlopába. Töltsd fel a programon készült képeket: ehhez hozz '
                'létre egy új mappát a „Program képek” mappába, és a mappa nevét írd be a táblázat „Képek” '
                'oszlopába. A beszámoló és a képek pár órán belül megjelennek a honlapon.')
    else:
        subject = f'Emlékeztető: még hiányzik {the_name} beszámolója'
        text = (f'Egy hete volt {the_name} ({date}), de a honlapra még nem került fel róla beszámoló. Kérünk, '
                'írd meg néhány mondatban a programos táblázat „Beszámoló” oszlopába, amint tudod. Ha vannak '
                'képeid a programról, azoknak hozz létre egy új mappát a „Program képek” mappában, és az új '
                'mappa nevét írd be a „Képek” oszlopba.')
    links = f'{LINKS}\n\n' if LINKS else ''
    body = f'{hello}\n\n{text}\n\n{links}{NO_REPLY}\n\nJó munkát!\n{SIGNATURE}\n'
    return re.sub(r'[\r\n]+', ' ', subject), body


def due(row, now, sent):
    """The kind of e-mail the program needs now, or None."""
    start, end = start_of(row), end_of(row)
    if 'photos' not in sent and now < start <= now + PHOTOS_AHEAD:
        return 'photos'
    if row['report'] or now > end + GIVE_UP_AFTER:
        return None
    if 'report_again' not in sent and now >= end + REPORT_AGAIN_AFTER:
        return 'report_again'
    if 'report' not in sent and 'report_again' not in sent and end + REPORT_AFTER <= now < end + REPORT_AGAIN_AFTER:
        return 'report'
    return None


class Mailer:
    def __init__(self):
        self.user = os.environ.get('SMTP_USER', '').strip()
        self.password = os.environ.get('SMTP_PASSWORD', '').replace(' ', '')
        self.host = os.environ.get('SMTP_HOST', '').strip() or 'smtp.gmail.com'
        self.port = int(os.environ.get('SMTP_PORT', '').strip() or 465)
        self.enabled = bool(self.user and self.password)
        self.server = None

    def send(self, to, subject, body):
        message = email.message.EmailMessage()
        message['From'] = email.utils.formataddr((SENDER_NAME, self.user))
        message['To'] = ', '.join(email.utils.formataddr(person) for person in to)
        message['Subject'] = subject
        message['Date'] = email.utils.formatdate(localtime=True)
        message['Message-ID'] = email.utils.make_msgid(domain=self.user.split('@')[-1])
        message.set_content(body)
        if self.server is None:
            self.server = smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=30)
            self.server.login(self.user, self.password)
        self.server.send_message(message)

    def close(self):
        if self.server is not None:
            with contextlib.suppress(Exception):
                self.server.quit()


def load_state():
    try:
        with open(STATE, encoding='utf-8') as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    common.save_snapshot(STATE, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', help='local CSV export of the Programok sheet (default: data/programs.csv)')
    parser.add_argument('--now', help='for testing: "YYYY-MM-DD HH:MM"')
    args = parser.parse_args()
    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now().replace(second=0, microsecond=0)

    with open(args.file or programs.SNAPSHOT, encoding='utf-8-sig') as handle:
        csv_text = handle.read()
    with contextlib.redirect_stdout(io.StringIO()):   # its warnings were already shown by sync_programs.py
        rows, _ = programs.parse_rows(csv_text)

    mailer = Mailer()
    if mailer.enabled and not SHEET_LINK:
        warn('Nincs beállítva a REMINDER_SHEET_LINK titok, a levelekből kimarad a táblázat linkje.')
    test_to = os.environ.get('REMINDER_TEST_TO', '').strip()
    try:
        if test_to:
            test(rows, now, mailer, test_to)
        else:
            run(rows, now, mailer)
    finally:
        mailer.close()


def test(rows, now, mailer, test_to):
    if not programs.EMAIL.fullmatch(test_to):
        common.fail(f'A teszt e-mail cím nem érvényes: "{test_to}".')
    if not mailer.enabled:
        common.fail('Nincs beállítva az SMTP_USER / SMTP_PASSWORD titok, a tesztlevelek nem küldhetők el.')
    upcoming = [row for row in rows if start_of(row) > now] or rows
    if not upcoming:
        common.fail('Nincs program a táblázatban, amiből tesztlevelet lehetne írni.')
    row = upcoming[0]
    people = recipients(row) or [('', test_to)]
    for kind in ('photos', 'report', 'report_again'):
        subject, body = compose(kind, row, people)
        mailer.send([('', test_to)], f'[TESZT] {subject}', body)
        print(f'Tesztlevél elküldve: {subject}')
    print(f'3 tesztlevél elküldve (a "{row["name"]}" program alapján), a valódi címzettek nem kaptak levelet.')


def run(rows, now, mailer):
    state = load_state()
    sent_count = 0
    for row in rows:
        key = key_of(row)
        sent = state.get(key, {})
        kind = due(row, now, sent)
        if not kind:
            continue
        people = recipients(row)
        if not people:
            warn(f'{row["label"]}: nincs érvényes kapcsolattartói e-mail cím, az emlékeztető nem küldhető el.')
            continue
        subject, body = compose(kind, row, people)
        addresses = ', '.join(address for _, address in people)
        if not mailer.enabled:
            print(f'(SMTP nélkül nem küldöm el) {addresses}: {subject}')
            continue
        try:
            mailer.send(people, subject, body)
        except smtplib.SMTPAuthenticationError:
            save_state(state)   # keep what was sent before
            common.fail('Az SMTP bejelentkezés nem sikerült: ellenőrizd az SMTP_USER és SMTP_PASSWORD '
                        'titkot (Google-fióknál alkalmazásjelszó kell).')
        except (smtplib.SMTPException, OSError) as error:
            warn(f'{row["label"]}: az emlékeztető nem ment el ({type(error).__name__}: {error}); a következő futáskor újrapróbálom.')
            mailer.close()
            mailer.server = None
            continue
        state[key] = {**sent, kind: now.isoformat(timespec='minutes'), 'end': end_of(row).date().isoformat()}
        sent_count += 1
        print(f'Elküldve: {addresses}: {subject}')

    # forget long-finished programs
    limit = (now - KEEP_STATE).date().isoformat()
    state = {key: value for key, value in state.items() if value.get('end', '9999') >= limit}
    if mailer.enabled:
        save_state(state)
    print(f'{sent_count} emlékeztető elküldve.' if mailer.enabled else
          'Nincs beállítva az SMTP_USER / SMTP_PASSWORD titok, ezért levelet nem küldtem.')


if __name__ == '__main__':
    main()
