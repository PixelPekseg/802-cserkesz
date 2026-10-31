"""Shared fixtures of the unit tests (pytest).

The scripts live in tools/ and are imported as top-level modules. Every test runs on a temporary
copy of what it needs: pages, data files and image folders are redirected into tmp_path, and the
network (sheet downloads, Drive, Google Calendar, SMTP) is replaced by fakes.
"""
import csv
import io
import json
import os
import shutil
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))

import sync_common as common  # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """No real secrets, test choices or GitHub Actions settings leak into a test."""
    for name in list(os.environ):
        if name.startswith(('TEST_', 'ADMIN_', 'GOOGLE_', 'SMTP_', 'GITHUB_')) or name in (
                'ONLY_TESTS', 'SYNC_ISSUES_FILE', 'SHEETS_CACHE_DIR', 'TEAM_SHEET_URL', 'LEADERS_SHEET_URL',
                'FEES_SHEET_URL', 'DRIVE_IMAGES_FOLDER_ID', 'DRIVE_LEADERS_FOLDER_ID', 'DRIVE_PROGRAMS_FOLDER_ID', 'DRIVE_LOCAL_DIR', 'PROGRAM_CALENDAR_ID',
                'VEZETOK_WEBOLDAL_ADATOK_LINK', 'CSPK_WEBOLDAL_ADATOK_LINK', 'PROGRAM_KEPEK_MAPPA_LINK',
                'ALLOW_EMPTY'):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(common, 'ISSUES_FILE', '')
    monkeypatch.setattr(common, 'CACHE_DIR', '')
    monkeypatch.setattr(common, 'in_actions', False)
    monkeypatch.setattr(common, '_quiet', False)
    common._BOOKS.clear()
    common._OPENED.clear()


@pytest.fixture
def site(tmp_path, monkeypatch):
    """A temporary site root with a copy of the real pages (generated blocks included)."""
    for name in os.listdir(REPO):
        if name.endswith('.html'):
            shutil.copy(os.path.join(REPO, name), tmp_path / name)
    (tmp_path / 'data').mkdir()
    monkeypatch.setattr(common, 'ROOT', str(tmp_path))
    return tmp_path


def csv_text(rows):
    out = io.StringIO()
    csv.writer(out, lineterminator='\n').writerows(rows)
    return out.getvalue()


def xlsx_bytes(sheets):
    """An .xlsx workbook in memory: {sheet name: [[cell, …], …]}."""
    import openpyxl
    book = openpyxl.Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def read_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL: records the sent messages (FakeSMTP.sent)."""
    sent = []
    fail_login = False
    fail_send = None

    def __init__(self, *args, **kwargs):
        pass

    def login(self, user, password):
        if FakeSMTP.fail_login:
            import smtplib
            raise smtplib.SMTPAuthenticationError(535, b'bad credentials')

    def send_message(self, message):
        if FakeSMTP.fail_send:
            raise FakeSMTP.fail_send
        FakeSMTP.sent.append(message)

    def quit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def smtp(monkeypatch):
    """Fake SMTP server and admin credentials; returns the list of sent messages."""
    import smtplib
    FakeSMTP.sent, FakeSMTP.fail_login, FakeSMTP.fail_send = [], False, None
    monkeypatch.setattr(smtplib, 'SMTP_SSL', FakeSMTP)
    monkeypatch.setenv('ADMIN_EMAIL', 'admin@cserkesz.hu')
    monkeypatch.setenv('ADMIN_JELSZO', 'abcd efgh')
    return FakeSMTP


@pytest.fixture
def issues(tmp_path, monkeypatch):
    """The warnings / errors recorded during the test: a function returning them."""
    path = tmp_path / 'issues.jsonl'
    monkeypatch.setattr(common, 'ISSUES_FILE', str(path))

    def read():
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    return read


@pytest.fixture
def paths(site, monkeypatch):
    """Points every module's page / data / image paths into the temporary site root."""
    import importlib
    targets = {
        'sync_camps': {'PAGE': 'tabor.html', 'SNAPSHOT': 'data/camps.csv'},
        'sync_counters': {'SNAPSHOT': 'data/counters.csv'},
        'sync_notices': {'SNAPSHOT': 'data/notices.csv'},
        'sync_troops': {'PAGE': 'csatlakozom.html', 'FINANCE': 'penzugyek.html', 'SNAPSHOT': 'data/troops.csv'},
        'sync_leaders': {'INDEX': 'index.html', 'HOME': 'csapatotthon.html', 'FINANCE': 'penzugyek.html',
                         'SNAPSHOT': 'data/leaders.csv'},
        'sync_equipment': {'PAGE': 'eszkozok.html'},
        'sync_fees': {'PAGE': 'penzugyek.html'},
        'sync_gallery': {'PAGE': 'galeria.html', 'PROGRAM_STATE': 'data/program_images.json'},
        'sync_programs': {'PAGE': 'programok.html', 'SNAPSHOT': 'data/programs.csv'},
        'drive_photos': {'TEAM_DIR': 'images/webp/kozos/team', 'STATE': 'data/photos.json'},
        'program_images': {'DIR': 'images/webp/programok', 'STATE': 'data/program_images.json'},
    }
    for module_name, attrs in targets.items():
        module = importlib.import_module(module_name)
        for attr, rel in attrs.items():
            monkeypatch.setattr(module, attr, str(site.joinpath(*rel.split('/'))))
    import sync_equipment
    monkeypatch.setattr(sync_equipment, 'SNAPSHOTS', (str(site / 'data' / 'equipment.csv'),
                                                      str(site / 'data' / 'equipment_contacts.csv')))
    return site


def block(path, marker):
    """The generated part of a page between <!-- MARKER:START … --> and <!-- MARKER:END -->."""
    text = open(path, encoding='utf-8').read()
    return text.split(f'<!-- {marker}:START', 1)[1].split(f'<!-- {marker}:END -->', 1)[0]


def run_script(module, monkeypatch, *args):
    monkeypatch.setattr('sys.argv', [f'{module.__name__}.py', *map(str, args)])
    module.main()
