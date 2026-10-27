#!/usr/bin/env python3
"""Reminder e-mail to the team's address when the new troop's leaders are not on the website.

Every year a new troop (raj) starts in September (the 4th graders). On September 15 and October 15
(or on the first run in the 14 days after, as the hourly runs are irregular) it checks the snapshot
of the Rajok sheet (data/troops.csv, saved by sync_troops.py just before): if there is no shown
row with this school year as "Indulás éve", or it has no troop leader with a name and an e-mail
address or phone number, an e-mail goes to TO with the link of the "weboldal-adatok" sheet (the team workbook). Each
occasion is sent once a year: recorded in data/troop_reminder.json (committed by the workflow).

Environment:
    ADMIN_EMAIL, ADMIN_JELSZO   GitHub Secrets (the same account as send_reminders.py); without
                                them the e-mail is only printed (and not recorded)
    CSPK_WEBOLDAL_ADATOK_LINK   the edit link of the team's sheet (GitHub Secret)
    REMINDER_TEST_TO            test: sends the e-mail to this address only, whatever the date
                                (nothing is recorded)

Usage:
    python tools/troop_reminder.py
    python tools/troop_reminder.py --today 2026-09-15   # for testing: a different "today"
    python tools/troop_reminder.py --file x.csv         # from a local CSV export of the Rajok sheet
"""
import argparse
import datetime as dt
import json
import os
import re
import smtplib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
import sync_troops as troops  # noqa: E402
from send_reminders import Mailer, SIGNATURE, programs  # noqa: E402

TO = ('802. sz. Szent Korona Cserkészcsapat', '802@cserkesz.hu')
STATE = os.path.join(common.ROOT, 'data', 'troop_reminder.json')
SHEET_LINK = os.environ.get('CSPK_WEBOLDAL_ADATOK_LINK', '').strip()
OCCASIONS = ((9, 15), (10, 15))   # (month, day)
WINDOW = dt.timedelta(days=14)


def due_occasion(today, state):
    """The key ("2026-09-15") of the occasion to send now, or None."""
    for month, day in OCCASIONS:
        date = dt.date(today.year, month, day)
        if date <= today < date + WINDOW and date.isoformat() not in state:
            return date.isoformat()
    return None


def new_troop_problem(csv_text, today):
    """'' if the new troop and a leader's contact are on the sheet, otherwise what is missing."""
    year = troops.school_year(today)
    rows = []
    for _, row in common.read_table(csv_text, troops.COLUMNS, required=['name', 'year', 'visible']):
        match = re.search(r'\d{4}', row['year'])
        if match and int(match.group()) == year and not common.is_hidden(row['visible']):
            rows.append(row)
    if not rows:
        return f'nincs olyan megjelenő raj a táblázatban, amelynek „Indulás éve” {year}'
    for row in rows:
        for i in (1, 2, 3):
            if row.get(f'n{i}') and (row.get(f'e{i}') or row.get(f't{i}')):
                return ''
    names = ', '.join(row['name'] or 'névtelen' for row in rows)
    return f'a(z) {names} sorában nincs rajparancsnok névvel és e-mail címmel vagy telefonszámmal'


def compose(today, problem, again):
    year = troops.school_year(today)
    subject = (f'{"Emlékeztető: hiányzik" if again else "Hiányzik"} az új raj rajparancsnokainak '
               'elérhetősége a weboldalról')
    link = f'\n\nweboldal-adatok táblázat: {SHEET_LINK}' if SHEET_LINK else ''
    body = (f'Sziasztok!\n\n'
            f'A weboldal Csatlakozom oldalán még nem szerepel a {year}/{str(year + 1)[-2:]}-es tanévben '
            f'induló új raj (a 4. osztályosok) rajparancsnokainak elérhetősége: {problem}.\n\n'
            'Kérünk, töltsétek ki a „weboldal-adatok” táblázat „Rajok” lapján az új raj sorát: a raj nevét, '
            f'az indulás évét ({year}) és legalább egy rajparancsnok nevét és e-mail címét (a telefonszám '
            'opcionális), hogy megjelenjen a weboldalon. A változás pár órán belül kikerül a Csatlakozom '
            f'oldalra és a Pénzügyek oldal Kcs tábordíj fülére.{link}\n\n'
            f'Jó munkát!\n{SIGNATURE}\n')
    return subject, body


def load_state():
    try:
        with open(STATE, encoding='utf-8') as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', help='local CSV export of the Rajok sheet (default: data/troops.csv)')
    parser.add_argument('--today', help='for testing: "YYYY-MM-DD"')
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    test_to = os.environ.get('REMINDER_TEST_TO', '').strip()

    state = load_state()
    occasion = due_occasion(today, state)
    if not occasion and not test_to:
        print('Ma nincs esedékes rajparancsnoki emlékeztető.')
        return
    with open(args.file or troops.SNAPSHOT, encoding='utf-8-sig') as handle:
        problem = new_troop_problem(handle.read(), today)
    if test_to:
        problem = problem or 'nincs hiány (ez csak egy tesztlevél)'
    elif not problem:
        print('Az új raj rajparancsnokainak elérhetősége megvan, nem kell levelet küldeni.')
        if occasion:
            common.save_snapshot(STATE, json.dumps({**state, occasion: 'nem kellett'}, ensure_ascii=False,
                                                    indent=2, sort_keys=True) + '\n')
        return

    subject, body = compose(today, problem, again=bool(occasion and occasion[5:7] == '10'))
    mailer = Mailer()
    if not mailer.enabled:
        print(f'(SMTP nélkül nem küldöm el) {TO[1]}: {subject}\n\n{body}')
        return
    if not SHEET_LINK:
        common.warn('Nincs beállítva a CSPK_WEBOLDAL_ADATOK_LINK titok, a levélből kimarad a táblázat linkje.')
    if test_to and not programs.EMAIL.fullmatch(test_to):
        common.fail(f'A teszt e-mail cím nem érvényes: "{test_to}".')
    try:
        mailer.send([('', test_to)] if test_to else [TO], f'[TESZT] {subject}' if test_to else subject, body)
    except smtplib.SMTPAuthenticationError:
        common.fail('Az SMTP bejelentkezés nem sikerült: ellenőrizd az ADMIN_EMAIL és ADMIN_JELSZO titkot.')
    except (smtplib.SMTPException, OSError) as error:
        common.warn(f'A rajparancsnoki emlékeztető nem ment el ({type(error).__name__}: {error}); '
                    'a következő futáskor újrapróbálom.')
        return
    finally:
        mailer.close()
    if test_to:
        print(f'Tesztlevél elküldve ide: {test_to}: {subject}')
        return
    common.save_snapshot(STATE, json.dumps({**state, occasion: dt.datetime.now().isoformat(timespec='minutes')},
                                           ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(f'Elküldve: {TO[1]}: {subject}')


if __name__ == '__main__':
    main()
