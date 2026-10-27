#!/usr/bin/env python3
"""Keeps the public "802. Programok" Google Calendar in step with the Programok sheet.

Reads data/programs.csv (the snapshot sync_programs.py has just saved; the same programs as on
the Programjaink page) and, through the Google Calendar API, adds the new programs, updates the
changed ones and deletes the ones no longer on the sheet. Every program gets a fixed event id
(from its name and date, as the card id on the page), so nothing is duplicated; only the events
this script made (extendedProperties.private.source) are touched, events added by hand stay.
People subscribe to the calendar (button on the Programjaink page), so their own calendars
follow the changes.

Signs in as a Google Cloud service account that the calendar is shared with ("Make changes to
events"):
    GOOGLE_SERVICE_ACCOUNT_KEY   the service account's JSON key (GitHub Secret); without it the
                                 calendar is not touched (a warning)
    PROGRAM_CALENDAR_ID          the calendar's id (not a secret)
    SITE_URL                     the site's address, for the link in the events

Usage:
    python tools/sync_calendar.py
    python tools/sync_calendar.py --dry-run     # prints what it would change (needs the key too)
    python tools/sync_calendar.py --show        # prints the events built from the sheet, no API
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402
import sync_programs as programs  # noqa: E402

API = 'https://www.googleapis.com/calendar/v3'
SCOPE = 'https://www.googleapis.com/auth/calendar.events'
SOURCE = '802-weboldal'
TIME_ZONE = 'Europe/Budapest'
COLOR = '10'    # "Basil" (dark green) in Google Calendar's event colours
DEFAULT_LENGTH = dt.timedelta(hours=1)   # a program with only a start time (as for "Google Naptárba")
SITE_URL = os.environ.get('SITE_URL', 'https://pixelpekseg.github.io/802-cserkesz/').rstrip('/') + '/'

warn, fail = common.warn, common.fail


# ---------- the events from the sheet ----------

def event_id(card_id):
    # Calendar event ids may use the characters a-v and 0-9 (base32hex): a hex digest fits
    return 'p802' + hashlib.sha256(card_id.encode()).hexdigest()[:32]


def when(row):
    """(start, end) in the Calendar API format: all-day (date) or timed (dateTime)."""
    first, last = row['start'], row['end'] or row['start']
    if not row['start_time']:
        return {'date': first.isoformat()}, {'date': (last + dt.timedelta(days=1)).isoformat()}
    start = dt.datetime.combine(first, dt.time.fromisoformat(row['start_time']))
    if row['end_time']:
        end = dt.datetime.combine(last, dt.time.fromisoformat(row['end_time']))
        if end <= start:
            end += dt.timedelta(days=1)   # overnight, e.g. 22:00–02:00
    else:
        end = start + DEFAULT_LENGTH
    return ({'dateTime': start.isoformat(timespec='minutes') + ':00', 'timeZone': TIME_ZONE},
            {'dateTime': end.isoformat(timespec='minutes') + ':00', 'timeZone': TIME_ZONE})


def description(row, card_id):
    parts = []
    text = (row['report'] if row['report'] and (row['end'] or row['start']) < dt.date.today()
            else row['description']).strip()
    if text:
        parts.append(text)
    if row['time_note'] and row['start_time']:
        parts.append(f'Időpont: {row["start_time"]} ({row["time_note"]})')
    contacts = []
    for i in ('1', '2'):
        name, email, phone = row[f'c{i}_name'], row[f'c{i}_email'], common.fix_phone(row[f'c{i}_phone'])
        details = ', '.join(v for v in (email, phone) if v)
        if name or details:
            contacts.append(f'{name} ({details})' if name and details else name or details)
    if contacts:
        parts.append('Kérdés esetén keresd: ' + '; '.join(contacts))
    if row['facebook']:
        parts.append(f'Facebook-esemény: {row["facebook"]}')
    parts.append(f'Részletek a weboldalon: {SITE_URL}programok.html#{card_id}')
    return '\n\n'.join(parts)


def build_events(rows):
    """{event id: event body} of every program on the sheet."""
    events = {}
    for row, card_id in zip(rows, programs.card_ids(rows)):
        start, end = when(row)
        body = {
            'summary': row['name'],
            'location': row['place'],
            'description': description(row, card_id),
            'start': start, 'end': end,
            'colorId': COLOR,
            'transparency': 'transparent',   # does not mark the subscribers as busy
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        body['id'] = event_id(card_id)
        body['status'] = 'confirmed'
        body['extendedProperties'] = {'private': {'source': SOURCE, 'card': card_id, 'hash': digest}}
        events[body['id']] = body
    return events


# ---------- the Calendar API ----------

def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def access_token(key):
    """OAuth access token of the service account (a signed JWT exchanged at Google)."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        fail('Hiányzik a cryptography csomag (pip install -r tools/requirements.txt).')
    now = int(time.time())
    claims = {'iss': key['client_email'], 'scope': SCOPE, 'aud': key['token_uri'], 'iat': now, 'exp': now + 3600}
    unsigned = b64(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode()) + '.' + b64(json.dumps(claims).encode())
    try:
        private_key = serialization.load_pem_private_key(key['private_key'].encode(), password=None)
    except (ValueError, TypeError):
        fail('A GOOGLE_SERVICE_ACCOUNT_KEY titokban lévő kulcs sérült (a teljes JSON kulcsfájl kell bele, változtatás nélkül).')
    signature = private_key.sign(unsigned.encode(), padding.PKCS1v15(), hashes.SHA256())
    data = urllib.parse.urlencode({'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                                   'assertion': unsigned + '.' + b64(signature)}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(key['token_uri'], data=data), timeout=30) as response:
            return json.loads(response.read())['access_token']
    except urllib.error.HTTPError as error:
        fail(f'A robotfiók bejelentkezése nem sikerült (HTTP {error.code}): ellenőrizd a '
             'GOOGLE_SERVICE_ACCOUNT_KEY titkot (a teljes JSON kulcsfájl kell bele).')


class Calendar:
    def __init__(self, token, calendar_id):
        self.token = token
        self.base = f'{API}/calendars/{urllib.parse.quote(calendar_id, safe="")}/events'

    def call(self, method, path='', body=None, query=None):
        url = self.base + path + (f'?{urllib.parse.urlencode(query)}' if query else '')
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read()
            return json.loads(text) if text else {}

    def ours(self):
        """{event id: event} of the events this script made (cancelled ones included)."""
        events, token = {}, None
        while True:
            query = {'privateExtendedProperty': f'source={SOURCE}', 'showDeleted': 'true', 'maxResults': 2500}
            if token:
                query['pageToken'] = token
            page = self.call('GET', query=query)
            for event in page.get('items', []):
                events[event['id']] = event
            token = page.get('nextPageToken')
            if not token:
                return events


def http_error_text(error):
    try:
        return json.loads(error.read()).get('error', {}).get('message', '')
    except Exception:
        return ''


def sync(calendar, wanted, dry_run=False):
    existing = calendar.ours()
    added = updated = deleted = 0
    for event_id_, body in wanted.items():
        old = existing.get(event_id_)
        if old and old.get('status') != 'cancelled' and \
                old.get('extendedProperties', {}).get('private', {}).get('hash') == \
                body['extendedProperties']['private']['hash']:
            continue
        label = f'{body["summary"]} ({body["start"].get("date") or body["start"]["dateTime"][:10]})'
        if dry_run:
            common.say(f'{"Frissíteném" if old else "Felvenném"}: {label}')
            continue
        try:
            if old:   # also brings back an event deleted earlier (its id cannot be used again)
                calendar.call('PUT', f'/{event_id_}', body)
                updated += 1
            else:
                calendar.call('POST', body=body)
                added += 1
        except urllib.error.HTTPError as error:
            if error.code == 409:   # the id exists but was not listed (e.g. deleted long ago)
                try:
                    calendar.call('PUT', f'/{event_id_}', body)
                    updated += 1
                    continue
                except urllib.error.HTTPError as again:
                    error = again
            if error.code in (401, 403):
                fail(f'A naptár írása nem engedélyezett (HTTP {error.code}: {http_error_text(error)}). '
                     'Meg van osztva a naptár a robotfiókkal „Módosítások végrehajtása és az összes '
                     'eseményrészlet megtekintése” joggal, és be van kapcsolva a Google Calendar API?')
            warn(f'{label}: a naptárba írás nem sikerült (HTTP {error.code}: {http_error_text(error)}).')
    for event_id_, old in existing.items():
        if event_id_ in wanted or old.get('status') == 'cancelled':
            continue
        if dry_run:
            common.say(f'Törölném: {old.get("summary", event_id_)}')
            continue
        try:
            calendar.call('DELETE', f'/{event_id_}')
            deleted += 1
        except urllib.error.HTTPError as error:
            if error.code != 410:   # 410: already deleted
                warn(f'{old.get("summary", event_id_)}: a törlés nem sikerült (HTTP {error.code}).')
    return added, updated, deleted


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', help='local CSV export of the Programok sheet (default: data/programs.csv)')
    parser.add_argument('--dry-run', action='store_true', help='print the changes, do not write the calendar')
    parser.add_argument('--show', action='store_true', help='print the events built from the sheet (no API)')
    args = parser.parse_args()

    with open(args.file or programs.SNAPSHOT, encoding='utf-8-sig') as handle:
        csv_text = handle.read()
    with common.quiet():   # its warnings were already reported by sync_programs.py
        rows, _ = programs.parse_rows(csv_text)
    wanted = build_events(rows)
    if args.show:
        for body in wanted.values():
            print(json.dumps(body, ensure_ascii=False, indent=2))
        return

    raw_key = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY', '').strip()
    calendar_id = os.environ.get('PROGRAM_CALENDAR_ID', '').strip()
    if not raw_key or not calendar_id:
        warn('Nincs beállítva a GOOGLE_SERVICE_ACCOUNT_KEY titok vagy a PROGRAM_CALENDAR_ID, a Google '
             'Naptárat most nem frissítem.')
        return
    try:
        key = json.loads(raw_key)
        key['client_email'], key['private_key'], key.setdefault('token_uri', 'https://oauth2.googleapis.com/token')
    except (json.JSONDecodeError, KeyError, TypeError):
        fail('A GOOGLE_SERVICE_ACCOUNT_KEY titok nem a robotfiók JSON kulcsfájlja (a teljes fájltartalom kell '
             'bele, a { … } jelekkel együtt).')
    if not wanted and not os.environ.get('ALLOW_EMPTY'):
        fail('Egyetlen program sincs a táblázatban, ezért nem ürítem ki a naptárat.')

    try:
        calendar = Calendar(access_token(key), calendar_id)
        added, updated, deleted = sync(calendar, wanted, dry_run=args.dry_run)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403, 404):
            fail(f'A naptár nem érhető el (HTTP {error.code}: {http_error_text(error)}). Jó a PROGRAM_CALENDAR_ID, '
                 'és meg van osztva a naptár a robotfiókkal?')
        fail(f'A Google Naptár most nem válaszolt rendesen (HTTP {error.code}); a következő futás újrapróbálja.')
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        fail(f'A Google Naptár most nem érhető el ({getattr(error, "reason", error)}); a következő futás újrapróbálja.')
    if not args.dry_run:
        print(f'Google Naptár: {len(wanted)} program; új: {added}, frissített: {updated}, törölt: {deleted}.')


if __name__ == '__main__':
    main()
