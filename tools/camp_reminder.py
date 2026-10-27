#!/usr/bin/env python3
"""Monthly reminder e-mail while a camp card misses some of its required details.

From March 1 to August 1, once a month (on the first run of the 1st–14th of the month, as the
hourly runs are irregular), it checks the snapshot of the Táborok sheet (data/camps.csv, saved by
sync_camps.py just before). Required on every shown camp card: the time (Időpont), the place
(Helyszín), at least two main organisers (Főszervező) and at least one contact (an e-mail address
or phone number of a main organiser). If something is missing, an e-mail goes to the deputy team
leader responsible for camps and programs (the Csapatvezetés row whose role contains "tábor";
data/leaders.csv), otherwise to the team's address, with the link of the team's sheet. Each month
is handled once: recorded in data/camp_reminder.json (committed by the workflow).

Environment:
    ADMIN_EMAIL, ADMIN_JELSZO   GitHub Secrets (the same account as send_reminders.py); without
                                them the e-mail is only printed (and not recorded)
    CSPK_WEBOLDAL_ADATOK_LINK   the edit link of the team's sheet (GitHub Secret)
    TEST_CAMP, TEST_CAMP_TO     test (Run workflow form): sends the e-mail, marked [TESZT], to the
                                given address or without one to the real recipient, whatever the
                                date (nothing is recorded)

Usage:
    python tools/camp_reminder.py
    python tools/camp_reminder.py --today 2027-03-01      # for testing: a different "today"
    python tools/camp_reminder.py --file t.csv            # from a local CSV export of the Táborok sheet
"""
import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
import sync_camps as camps  # noqa: E402
import sync_leaders as leaders  # noqa: E402
from mailing import SIGNATURE, greeting, periodic_reminder  # noqa: E402

FALLBACK_TO = ('802. sz. Szent Korona Cserkészcsapat', '802@cserkesz.hu')
STATE = os.path.join(common.ROOT, 'data', 'camp_reminder.json')
SHEET_LINK = os.environ.get('CSPK_WEBOLDAL_ADATOK_LINK', '').strip()
MONTHS = range(3, 9)               # March 1 … August 1
WINDOW = dt.timedelta(days=14)
ROLE_WORD = 'tábor'                # "Tábor és programok"


def due_month(today, state):
    """The key ("2027-03") of the month to handle now, or None."""
    if today.month not in MONTHS:
        return None
    first = today.replace(day=1)
    key = f'{today:%Y-%m}'
    return key if today < first + WINDOW and key not in state else None


def filled(value):
    """Not empty and not a placeholder ("Hamarosan frissítjük!", "hamarosan", "-", "?" …)."""
    value = (value or '').strip().strip('.!?-–— ').lower()
    return bool(value) and not value.startswith(('hamarosan', 'később', 'kesobb', 'tbd', 'nincs még', 'még nincs'))


def camp_problems(csv_text):
    """[(camp name, [missing details])] of the shown camp cards that miss something."""
    result = []
    for _, row in common.read_table(csv_text, camps.COLUMNS, required=['name', 'visible']):
        if common.is_hidden(row['visible']) or not row['name']:
            continue
        missing = []
        if not filled(row.get('time')):
            missing.append('az időpont')
        if not filled(row.get('place')):
            missing.append('a helyszín')
        organisers = [i for i in (1, 2, 3) if filled(row.get(f'n{i}'))]
        if len(organisers) < 2:
            missing.append(f'legalább két főszervező neve (most {len(organisers)} van megadva)')
        if not any(filled(row.get(f'e{i}')) or filled(row.get(f't{i}')) for i in (1, 2, 3)):
            missing.append('legalább egy elérhetőség (egy főszervező e-mail címe vagy telefonszáma)')
        if missing:
            result.append((row['name'], missing))
    return result


def recipient():
    """(name, address) of the deputy responsible for camps, from the Csapatvezetés snapshot."""
    try:
        with open(leaders.SNAPSHOT, encoding='utf-8-sig') as handle:
            table = common.read_table(handle.read(), leaders.COLUMNS, required=['name', 'role', 'visible'])
    except (OSError, SystemExit):
        return None
    for _, row in table:
        with common.quiet():   # sync_leaders.py already reported the sheet's problems
            address = common.first_email(row.get('email'), '')
        if ROLE_WORD in (row.get('role') or '').lower() and common.EMAIL.fullmatch(address):
            return row['name'], address
    return None


def compose(person, problems):
    hello = greeting([person[0]] if person else [])
    lines = [f'- {name}: hiányzik {", ".join(missing)}' for name, missing in problems]
    link = f'\n\nweboldal-adatok táblázat: {SHEET_LINK}' if SHEET_LINK else ''
    subject = 'Hiányzó adatok a tábor kártyákon a weboldalon'
    body = (f'{hello}\n\n'
            'A weboldal Táboraink oldalán még nem teljesek a tábor kártyák. Minden táborhoz kötelező: '
            'az időpont, a helyszín, legalább két főszervező és legalább egy elérhetőség (e-mail cím vagy '
            'telefonszám).\n\n'
            'Ezek hiányoznak:\n' + '\n'.join(lines) + '\n\n'
            'Kérünk, töltsd ki őket a „weboldal-adatok” táblázat „Táborok” lapján; pár órán belül megjelennek '
            'a weboldalon. Amíg valami hiányzik, augusztus 1-ig minden hónap elején emlékeztetünk.'
            f'{link}\n\nJó munkát!\n{SIGNATURE}\n')
    return subject, body


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', help='local CSV export of the Táborok sheet (default: data/camps.csv)')
    parser.add_argument('--today', help='for testing: "YYYY-MM-DD"')
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    def build(test):
        with open(args.file or camps.SNAPSHOT, encoding='utf-8-sig') as handle:
            problems = camp_problems(handle.read())
        if not problems and not test:
            return None
        person = recipient()
        if not person:
            common.warn('Nem találtam a Csapatvezetés lapon érvényes e-mail címmel azt, akinek a szerepében a '
                        '„tábor” szó szerepel; a 802@cserkesz.hu-ra küldöm.')
        problems = problems or [('(teszt)', ['semmi, ez csak egy tesztlevél'])]
        return ([person or FALLBACK_TO], *compose(person, problems))

    periodic_reminder('CAMP', 'Tábori emlékeztető', STATE, lambda state: due_month(today, state), build)


if __name__ == '__main__':
    main()
