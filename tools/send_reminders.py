#!/usr/bin/env python3
"""Reminder e-mails about the programs (Programok sheet) to the organisers and the team's media person.

    1. photos:       the program starts within the next 24 hours
    2. report:       1 day after the end, if the Beszámoló column is still empty
    3. report_again: 1 week after the end, if it is still empty

The organisers (Kapcsolattartó 1/2 e-mail, required for upcoming programs, see sync_programs.py)
get 1. and 2.: take photos, write a report and send both to the media person (no sheet link).
The media person ("Médiás kapcsolat" sheet of the leaders' workbook) gets all three: which program
it is, who organises it, and to ask them for the report and the photos, which the media person
puts on the website (with the links of the sheet and the image folder). Everybody is addressed by
their given name. Each e-mail is sent only once: the sent ones are recorded in data/reminders.json
(committed by the workflow); without a media person nothing is sent (a warning, retried next run).

Reads data/programs.csv, the snapshot that sync_programs.py has just saved, so the sheet is not
downloaded twice; the media person is read from the leaders' workbook (LEADERS_SHEET_URL).
Sends through SMTP (Gmail / Google Workspace: an app password):
    ADMIN_EMAIL, ADMIN_JELSZO     GitHub Secrets: the sending account and its app password; without
                                  them nothing is sent, the would-be e-mails are only listed
                                  (and not recorded)
    SMTP_HOST, SMTP_PORT          optional, default smtp.gmail.com:465 (SSL)
    VEZETOK_WEBOLDAL_ADATOK_LINK  the edit link of the leaders' sheet, put into the media person's
                                  e-mails (GitHub Secret)
    PROGRAM_KEPEK_MAPPA_LINK      the link of the Drive image folder (GitHub Secret)
    TEST_ORGANISER, TEST_MEDIA    test ("true", from the Run workflow form): sends the organisers' (2)
    TEST_ORGANISER_TO, …_TO       or the media person's (3) e-mails of the next program, marked
                                  [TESZT], to the given address, or without one to the real
                                  recipients; nothing else is sent, nothing is recorded

Usage:
    python tools/send_reminders.py
    python tools/send_reminders.py --now "2026-11-07 10:00"   # for testing: a different "now"
    python tools/send_reminders.py --file x.csv               # from a local CSV export
    python tools/send_reminders.py --xlsx v.xlsx              # media person from a local workbook copy
    python tools/send_reminders.py --media-file m.csv         # media person from a local CSV export
"""
import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
import sync_programs as programs  # noqa: E402
from mailing import SIGNATURE, Mailer, greeting, join_and, test_mail, test_target, testing  # noqa: E402

STATE = os.path.join(common.ROOT, 'data', 'reminders.json')
# The edit link of the sheet and the link of the image folder are GitHub Secrets as well: the
# repository is public, and they may give edit access to whoever has them.
SHEET_LINK = os.environ.get('VEZETOK_WEBOLDAL_ADATOK_LINK', '').strip()
IMAGES_LINK = os.environ.get('PROGRAM_KEPEK_MAPPA_LINK', '').strip()

PHOTOS_AHEAD = dt.timedelta(hours=24)
REPORT_AFTER = dt.timedelta(days=1)
REPORT_AGAIN_AFTER = dt.timedelta(days=7)
# a program that ended longer ago gets no e-mail any more (e.g. old rows when the feature starts)
GIVE_UP_AFTER = dt.timedelta(days=14)
DEFAULT_START = dt.time(8, 0)     # an all-day program counts as starting at 8:00
KEEP_STATE = dt.timedelta(days=60)
MEDIA_SHEET = 'Médiás kapcsolat'
MEDIA_COLUMNS = {'name': 'név', 'role': 'szerep', 'email': 'e-mail', 'phone': 'telefon'}

warn = common.warn


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
        if address and common.EMAIL.fullmatch(address) and address.lower() not in [a.lower() for _, a in result]:
            result.append((name, address))
    return result


def media_people(csv_text):
    """[(name, address, phone)] of the media person(s): every row with a name and a valid e-mail."""
    result = []
    for line_number, row in common.read_table(csv_text, MEDIA_COLUMNS, required=['name', 'email']):
        address = row['email'].strip()
        if not row['name'] or not common.EMAIL.fullmatch(address):
            warn(f'{MEDIA_SHEET}, {line_number}. sor: hiányzik a név vagy az érvényes e-mail cím, kihagyva.')
            continue
        result.append((row['name'], address, common.fix_phone(row.get('phone', '')).strip()))
    return result


def person_text(people, with_phone=False):
    """"Kiss Anna (anna@…)" / "Kiss Anna (anna@…) és Nagy Béla (bela@…)"."""
    parts = []
    for person in people:
        details = [person[1]] + ([person[2]] if with_phone and len(person) > 2 and person[2] else [])
        parts.append(f'{person[0] or person[1]} ({", ".join(details)})')
    return join_and(parts)


def when_text(row):
    parts = [programs.display_date(row['start'], row['end'])]
    if row['start_time']:
        parts.append(row['start_time'] + (f'–{row["end_time"]}' if row['end_time'] else ''))
    if row['place']:
        parts.append(row['place'])
    return ', '.join(parts)


LINKS = '\n'.join(line for line in (f'Programos táblázat: {SHEET_LINK}' if SHEET_LINK else '',
                                    f'Program képek mappa: {IMAGES_LINK}' if IMAGES_LINK else '') if line)


def with_article(name):
    """The name with its Hungarian definite article: "az Őszi portya", "a Cserkészmise"."""
    return f'{common.article(name)} {name}'


def compose_organiser(kind, row, people, media):
    """(subject, body) of the e-mail to the organisers (kind: photos or report)."""
    name, date = row['name'], programs.display_date(row['start'], row['end'])
    the_name = with_article(name)
    to_media = f'a csapat médiásának: {person_text(media, with_phone=True)}'
    if kind == 'photos':
        subject = f'Hamarosan kezdődik: {name} – ne felejts el képeket készíteni!'
        text = (f'Hamarosan kezdődik {the_name} ({when_text(row)}), melyhez te vagy feltüntetve szervezőként.\n\n'
                'Kérünk, hogy készíts (vagy kérj meg valakit, hogy készítsen) néhány képet a programról, és a '
                'program után írj egy rövid beszámolót arról, hogyan sikerült.\n'
                f'A képeket és a beszámolót küldd el {to_media}. Ő teszi fel őket a weboldalra.')
    else:
        subject = f'Hogy sikerült {the_name}? Küldd el a beszámolót és a képeket!'
        text = (f'Reméljük, jól sikerült {the_name} ({date})! Kérünk, írj róla néhány mondatos beszámolót, '
                f'és a programon készült képekkel együtt küldd el {to_media}. Ő teszi fel őket a weboldalra.\n\n'
                'Ha már elküldted, ezt a levelet nyugodtan hagyd figyelmen kívül.')
    return finish(subject, f'{greeting([p[0] for p in people], "Kedves Kapcsolattartó!")}\n\n{text}\n\n', '')


def compose_media(kind, row, people, media):
    """(subject, body) of the e-mail to the media person (kind: photos, report or report_again)."""
    name, date = row['name'], programs.display_date(row['start'], row['end'])
    the_name = with_article(name)
    if people:
        several = len(people) > 1
        organisers = f'A program {"szervezői" if several else "szervezője"}: {person_text(people)}.'
        ask = 'tőlük' if several else 'tőle'
        whom = 'a szervezőket' if several else 'a szervezőt'
        told = 'A szervezőknek' if several else 'A szervezőnek'
    else:
        organisers = 'A programhoz nincs megadva szervező a táblázatban.'
        ask, whom, told, several = 'a szervezőktől', 'a program szervezőit', '', True
    upload = ('A képeknek készíts egy almappát a „Program képek” mappába, és töltsd fel őket oda, majd a mappa '
              'nevét írd be a programos táblázat „Képek” oszlopába. A beszámolót a táblázat „Beszámoló” '
              'oszlopába írd; a beszámoló és a képek pár órán belül megjelennek a honlapon.')
    if kind == 'photos':
        subject = f'Hamarosan kezdődik: {name} – kérj róla képeket és beszámolót!'
        text = (f'Hamarosan kezdődik {the_name} ({when_text(row)}). {organisers}\n\n'
                f'Kérünk, hogy a program után kérj {ask} képeket és egy rövid beszámolót, és tedd fel őket a '
                'weboldalra.' + (f' {told} is írtunk: azt kértük, hogy {"készítsenek" if several else "készítsen"} '
                                 f'képeket, és a beszámolóval együtt {"küldjék" if several else "küldje"} el neked.'
                                 if told else '') + '\n' + upload)
    elif kind == 'report':
        subject = f'Véget ért {the_name} – kérd el a beszámolót és a képeket!'
        text = (f'Véget ért {the_name} ({date}), de a táblázatban még nincs róla beszámoló. {organisers}\n\n'
                f'Ha még nem küldték el neked, kérünk, kérd el {ask} a beszámolót és a képeket'
                + (f' ({told.lower()} is küldtünk emlékeztetőt).' if told else '.') + '\n' + upload)
    else:
        subject = f'Emlékeztető: még hiányzik {the_name} beszámolója'
        text = (f'Egy hete volt {the_name} ({date}), de a honlapra még nem került fel róla beszámoló. '
                f'{organisers}\n\nKérünk, keresd meg {whom}, és ha megkaptad {ask} a beszámolót és a képeket, '
                'töltsd fel őket, hogy kitehessük a weboldalra.\n' + upload)
    return finish(subject, f'{greeting([p[0] for p in media], "Kedves Médiás!")}\n\n{text}\n\n', f'{LINKS}\n\n' if LINKS else '')


def finish(subject, text, links):
    return subject, f'{text}{links}Jó munkát!\n{SIGNATURE}\n'


# (state key, who gets it) of the e-mails of each stage
MESSAGES = {
    'photos': [('photos', 'media'), ('photos_organiser', 'organiser')],
    'report': [('report', 'media'), ('report_organiser', 'organiser')],
    'report_again': [('report_again', 'media')],
}


def messages(stage, row, media):
    """[(state key, recipients, subject, body)] of one stage; the organiser e-mail only with an organiser."""
    people = recipients(row)
    result = []
    for key, who in MESSAGES[stage]:
        if who == 'organiser':
            if people:
                result.append((key, people, *compose_organiser(stage, row, people, media)))
        else:
            result.append((key, [(n, a) for n, a, _ in media], *compose_media(stage, row, people, media)))
    return result


def due(row, now, sent):
    """The stage of e-mails the program needs now, or None. A stage is done when all its e-mails went out."""
    start, end = start_of(row), end_of(row)
    done = {stage: all(key in sent for key, _ in keys) for stage, keys in MESSAGES.items()}
    if not done['photos'] and now < start <= now + PHOTOS_AHEAD:
        return 'photos'
    if row['report'] or now > end + GIVE_UP_AFTER:
        return None
    if not done['report_again'] and now >= end + REPORT_AGAIN_AFTER:
        return 'report_again'
    if not done['report'] and 'report_again' not in sent and end + REPORT_AFTER <= now < end + REPORT_AGAIN_AFTER:
        return 'report'
    return None


# Before the media person was added, "photos" / "report" meant the e-mail to the organisers: those
# are not sent again (the media person does not get them for such a program either).
MEDIA_SINCE = '2026-10-27T12:00'


def load_state():
    state = common.load_json(STATE, {})
    for sent in state.values():
        for stage in ('photos', 'report'):
            if sent.get(stage, '9999') < MEDIA_SINCE:
                sent.setdefault(f'{stage}_organiser', sent[stage])
    return state


def save_state(state):
    common.save_json(STATE, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', help='local CSV export of the Programok sheet (default: data/programs.csv)')
    parser.add_argument('--now', help='for testing: "YYYY-MM-DD HH:MM"')
    parser.add_argument('--xlsx', help='local .xlsx copy of the leaders\' workbook (for the media person)')
    parser.add_argument('--media-file', help=f'local CSV export of the "{MEDIA_SHEET}" sheet (for testing)')
    args = parser.parse_args()
    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now().replace(second=0, microsecond=0)

    with open(args.file or programs.SNAPSHOT, encoding='utf-8-sig') as handle:
        csv_text = handle.read()
    with common.quiet():   # its warnings were already reported by sync_programs.py
        rows, _ = programs.parse_rows(csv_text)

    try:
        media_csv = common.fetch(argparse.Namespace(file=args.media_file, xlsx=args.xlsx), MEDIA_SHEET,
                                 book_env=common.LEADERS_SHEET_ENV)
        media = media_people(media_csv)
    except SystemExit:   # the sheet is missing or broken: the error was printed already
        media = []
    with Mailer() as mailer:
        if testing():
            test(rows, now, mailer, media)
            return
        if not media:
            warn(f'Nincs érvényes médiás a „{MEDIA_SHEET}” lapon (név + e-mail cím), ezért most egy emlékeztetőt '
                 'sem küldök; a következő futáskor újrapróbálom.')
            return
        if mailer.enabled and not SHEET_LINK:
            warn('Nincs beállítva a VEZETOK_WEBOLDAL_ADATOK_LINK titok, a médiás leveleiből kimarad a táblázat linkje.')
        run(rows, now, mailer, media)


def test(rows, now, mailer, media):
    """The test e-mails asked for on the Run workflow form, about the next program."""
    targets = {'organiser': test_target('ORGANISER'), 'media': test_target('MEDIA')}
    if all(target is None for target in targets.values()):
        print('Programos tesztlevél nem volt kérve; most rendes emlékeztető sem megy ki.')
        return
    if not mailer.enabled:
        common.fail('Nincs beállítva az ADMIN_EMAIL / ADMIN_JELSZO titok, a tesztlevelek nem küldhetők el.')
    upcoming = [row for row in rows if start_of(row) > now] or rows
    if not upcoming:
        common.fail('Nincs program a táblázatban, amiből tesztlevelet lehetne írni.')
    row = upcoming[0]
    if not media:
        warn(f'Nincs érvényes médiás a „{MEDIA_SHEET}” lapon; a szervezői levélben helyőrző áll, a médiás '
             'levelei csak teszt címre mehetnek.')
    shown_media = media or [('(a médiás még nincs megadva)', '-', '')]
    count = 0
    for stage in MESSAGES:
        for key, real, subject, body in messages(stage, row, shown_media):
            kind = 'media' if key in ('photos', 'report', 'report_again') else 'organiser'
            target = targets[kind]
            if target is None:
                continue
            if not target and kind == 'media' and not media:
                continue
            to, subject, body = test_mail(target, real, subject, body,
                                          'médiásnak' if kind == 'media' else 'szervezőnek')
            if mailer.deliver(to, subject, body, f'Tesztlevél ({subject})'):
                count += 1
                print(f'Tesztlevél elküldve ide: {", ".join(a for _, a in to)}: {subject}')
    print(f'{count} tesztlevél elküldve (a "{row["name"]}" program alapján); semmit nem rögzítettem.')


def run(rows, now, mailer, media):
    state = load_state()
    sent_count = 0
    for row in rows:
        key = key_of(row)
        sent = state.get(key, {})
        stage = due(row, now, sent)
        if not stage:
            continue
        if not recipients(row) and stage != 'report_again':
            warn(f'{row["label"]}: nincs érvényes kapcsolattartói e-mail cím, a szervező nem kap emlékeztetőt '
                 '(a médiás igen).')
        for message_key, people, subject, body in messages(stage, row, media):
            if message_key in sent:
                continue   # sent in an earlier run (e.g. the other e-mail of the stage failed then)
            addresses = ', '.join(address for _, address in people)
            if not mailer.enabled:
                print(f'(SMTP nélkül nem küldöm el) {addresses}: {subject}')
                continue
            if not mailer.deliver(people, subject, body, row['label'], on_auth_error=lambda: save_state(state)):
                continue
            sent = {**sent, message_key: now.isoformat(timespec='minutes'), 'end': end_of(row).date().isoformat()}
            state[key] = sent
            sent_count += 1
            print(f'Elküldve: {addresses}: {subject}')

    # forget long-finished programs
    limit = (now - KEEP_STATE).date().isoformat()
    state = {key: value for key, value in state.items() if value.get('end', '9999') >= limit}
    if mailer.enabled:
        save_state(state)
    print(f'{sent_count} emlékeztető elküldve.' if mailer.enabled else
          'Nincs beállítva az ADMIN_EMAIL / ADMIN_JELSZO titok, ezért levelet nem küldtem.')


if __name__ == '__main__':
    main()
