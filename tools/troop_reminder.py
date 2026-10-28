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
    TEST_TROOP, TEST_TROOP_TO   test (test-emails.yml form): sends the e-mail, marked [TESZT], to the
                                given address or without one to the real recipient, whatever the
                                date (nothing is recorded)

Usage:
    python tools/troop_reminder.py
    python tools/troop_reminder.py --today 2026-09-15   # for testing: a different "today"
    python tools/troop_reminder.py --file x.csv         # from a local CSV export of the Rajok sheet
"""
import argparse
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
import sync_troops as troops  # noqa: E402
from mailing import SIGNATURE, periodic_reminder  # noqa: E402

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
    subject = f'{"Emlékeztető: hiányoznak" if again else "Hiányoznak"} az új rajparancsnokok a weboldalról'
    link = f'\n\nWeboldal-adatok táblázat: {SHEET_LINK}' if SHEET_LINK else ''
    body = (f'Sziasztok!\n\n'
            f'A weboldal „Csatlakozom” fülén még nem szerepel a {year}/{str(year + 1)[-2:]}-es tanévben '
            f'induló új raj rajparancsnokainak elérhetősége: {problem}.\n\n'
            'Kérünk, töltsétek ki a „weboldal-adatok” táblázat „Rajok” lapján az új raj sorát: a raj nevét, '
            f'az indulás évét ({year}) és legalább egy rajparancsnok nevét és e-mail címét (a telefonszám '
            'opcionális), hogy megjelenjen a weboldalon. A változás pár órán belül kikerül a „Csatlakozom” '
            f'fülre és a „Pénzügyek” fül „Kcs tábordíj” részébe.{link}\n\n'
            f'Jó munkát!\n{SIGNATURE}\n')
    return subject, body


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', help='local CSV export of the Rajok sheet (default: data/troops.csv)')
    parser.add_argument('--today', help='for testing: "YYYY-MM-DD"')
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    def build(test):
        with open(args.file or troops.SNAPSHOT, encoding='utf-8-sig') as handle:
            problem = new_troop_problem(handle.read(), today)
        if not problem and not test:
            return None
        again = today.month == 10   # the October one is the second reminder
        return ([TO], *compose(today, problem or 'nincs hiány (ez csak egy tesztlevél)', again))

    periodic_reminder('TROOP', 'Rajparancsnoki emlékeztető', STATE, lambda state: due_occasion(today, state), build)


if __name__ == '__main__':
    main()
