#!/usr/bin/env python3
"""E-mails the admin about the problems of the hourly sync (the last step of the workflow).

Collects every warning and error the steps wrote (common.warn / common.fail, into SYNC_ISSUES_FILE)
and the steps that stopped with an unexpected error (STEPS_JSON, the workflow's steps context).
So that the same problems do not come every hour, it remembers what it reported
(data/sync_issues.json, committed by the workflow):
  - new problem(s) → an e-mail at once, with every current problem (the new ones marked);
  - the same problems still there → again once a day (after 23 hours);
  - every problem gone → one "minden rendben" e-mail.

Environment:
    ADMIN_EMAIL, ADMIN_JELSZO   the sending account; the report goes to the same address
    SYNC_ISSUES_FILE            the collected warnings / errors (one JSON line each)
    STEPS_JSON                  ${{ toJSON(steps) }} of the workflow (step id → outcome)

Usage:
    python tools/report_issues.py
    python tools/report_issues.py --dry-run     # prints the e-mail, does not send or save
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
from mailing import SIGNATURE, Mailer  # noqa: E402

STATE = os.path.join(common.ROOT, 'data', 'sync_issues.json')
REPEAT = dt.timedelta(hours=23)

# script → the part of the site it updates (as in the step names of the workflow)
SCRIPTS = {
    'sync_programs.py': 'Programok', 'sync_camps.py': 'Táborok', 'sync_troops.py': 'Rajok',
    'sync_notices.py': 'Értesítők', 'sync_counters.py': 'Számlálók', 'sync_leaders.py': 'Csapatvezetés',
    'sync_equipment.py': 'Eszközök', 'sync_fees.py': 'Pénzügyek', 'sync_gallery.py': 'Galéria',
    'send_reminders.py': 'Programos emlékeztetők', 'sync_calendar.py': 'Google Naptár',
    'troop_reminder.py': 'Rajparancsnoki emlékeztető', 'camp_reminder.py': 'Tábori emlékeztető',
    'sync_footer.py': 'Lábléc', 'check_site.py': 'Oldalellenőrzés',
}
# step id of the workflow → script
STEP_SCRIPTS = {
    'programs': 'sync_programs.py', 'camps': 'sync_camps.py', 'troops': 'sync_troops.py',
    'notices': 'sync_notices.py', 'counters': 'sync_counters.py', 'leaders': 'sync_leaders.py',
    'equipment': 'sync_equipment.py', 'fees': 'sync_fees.py', 'gallery': 'sync_gallery.py',
    'reminders': 'send_reminders.py', 'calendar': 'sync_calendar.py', 'troop_reminder': 'troop_reminder.py',
    'camp_reminder': 'camp_reminder.py', 'footer': 'sync_footer.py', 'check': 'check_site.py',
    'install': None,
}


def collect():
    """[(part, level, message)] of this run, without duplicates, in their order."""
    issues, scripts_with_error = [], set()
    path = os.environ.get('SYNC_ISSUES_FILE', '')
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                script = entry.get('script', '')
                if entry.get('level') == 'error':
                    scripts_with_error.add(script)
                issues.append((SCRIPTS.get(script, script), entry.get('level', 'warning'), entry.get('message', '')))
    try:
        steps = json.loads(os.environ.get('STEPS_JSON', '') or '{}')
    except json.JSONDecodeError:
        steps = {}
    for step_id, info in steps.items():
        if (info or {}).get('outcome') != 'failure':
            continue
        script = STEP_SCRIPTS.get(step_id, '')
        if script in scripts_with_error:
            continue   # its own error message is already in the list
        part = SCRIPTS.get(script, 'Csomagok telepítése' if step_id == 'install' else step_id)
        issues.append((part, 'error', 'a lépés váratlan hibával leállt (a részletek a GitHub Actions naplójában)'))
    return list(dict.fromkeys(issues))


def run_link():
    server, repo, run = (os.environ.get(k, '') for k in ('GITHUB_SERVER_URL', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID'))
    return f'{server}/{repo}/actions/runs/{run}' if server and repo and run else ''


def compose(issues, new_keys, solved):
    link = run_link()
    if solved:
        subject = '802 weboldal: minden frissítés rendben'
        body = ('Szia!\n\nA korábban jelzett problémák megszűntek, a legutóbbi frissítés hiba nélkül lefutott.'
                f'{chr(10) * 2 + "A futás: " + link if link else ""}\n\n{SIGNATURE}\n')
        return subject, body
    errors = sum(1 for _, level, _ in issues if level == 'error')
    subject = (f'802 weboldal: {errors} hiba és {len(issues) - errors} figyelmeztetés a frissítésnél' if errors
               else f'802 weboldal: {len(issues)} figyelmeztetés a frissítésnél')
    lines = []
    for part in dict.fromkeys(part for part, _, _ in issues):
        lines.append(f'{part}:')
        for p, level, message in issues:
            if p != part:
                continue
            mark = ('HIBA' if level == 'error' else 'figyelmeztetés') + (', ÚJ' if key_of(p, level, message) in new_keys else '')
            lines.append(f'  - [{mark}] {message}')
        lines.append('')
    body = ('Szia!\n\nAz óránkénti frissítés az alábbi problémákat találta. A „HIBA” azt jelenti, hogy az a rész '
            'most nem frissült (az oldalon a legutóbbi jó állapot maradt); a figyelmeztetésnél a rész frissült, '
            'de valamelyik adat hiányos vagy hibás volt a táblázatban (a sor száma és a lap neve az üzenetben).\n\n'
            + '\n'.join(lines) + '\n' +
            'Amíg a problémák fennállnak, naponta egyszer újra szólok; új probléma esetén azonnal.'
            f'{chr(10) * 2 + "A futás naplója: " + link if link else ""}\n\n{SIGNATURE}\n')
    return subject, body


def key_of(part, level, message):
    return f'{level}|{part}|{message}'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true', help='print the e-mail, do not send or save')
    args = parser.parse_args()
    now = dt.datetime.now().replace(second=0, microsecond=0)

    state = common.load_json(STATE, {})
    issues = collect()
    keys = [key_of(*issue) for issue in issues]
    old = set(state.get('issues', []))
    new_keys = set(keys) - old
    last = state.get('alerted')
    due_again = bool(keys) and (not last or now - dt.datetime.fromisoformat(last) >= REPEAT)

    if new_keys or due_again:
        subject, body = compose(issues, new_keys, solved=False)
    elif not keys and old:
        subject, body = compose([], set(), solved=True)
    else:
        print('Nincs új probléma, nem küldök levelet.' if keys else 'Minden frissítés rendben.')
        if set(keys) != old and not args.dry_run:   # some of them were solved: forget those
            save(keys, last)
        return

    if args.dry_run:
        print(f'Tárgy: {subject}\n\n{body}')
        return
    with Mailer() as mailer:
        if not mailer.enabled:
            print(f'(SMTP nélkül nem küldöm el) {subject}\n\n{body}')
            return
        try:
            mailer.send([('', mailer.user)], subject, body)
        except Exception as error:   # the report must not turn a good run red (and not report itself)
            print(f'::warning::A hibajelentő levél nem ment el ({type(error).__name__}: {error}).')
            return
    save(keys, now.isoformat(timespec='minutes') if keys else None)
    print(f'Hibajelentés elküldve: {subject}')


def save(keys, alerted):
    common.save_json(STATE, {'issues': keys, 'alerted': alerted})


if __name__ == '__main__':
    main()
