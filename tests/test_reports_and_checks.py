"""The run's report e-mail (report_issues), the page check (check_site) and the footer (sync_footer)."""
import datetime as dt
import json

import pytest

import check_site
import report_issues as report
import sync_footer as footer


# ---------- report_issues ----------

@pytest.fixture
def run(tmp_path, monkeypatch):
    """Writes this run's issue lines and steps; returns a function that runs the report at a time."""
    state = tmp_path / 'sync_issues.json'
    monkeypatch.setattr(report, 'STATE', str(state))
    issue_file = tmp_path / 'run.jsonl'

    def do(lines=(), steps=None, when=dt.datetime(2026, 11, 1, 10, 0), dry=False):
        issue_file.write_text(''.join(json.dumps(line) + '\n' for line in lines), encoding='utf-8')
        monkeypatch.setenv('SYNC_ISSUES_FILE', str(issue_file))
        monkeypatch.setenv('STEPS_JSON', json.dumps(steps or {}))

        class FixedDatetime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return when
        monkeypatch.setattr(report.dt, 'datetime', FixedDatetime)
        monkeypatch.setattr('sys.argv', ['report_issues.py'] + (['--dry-run'] if dry else []))
        report.main()
    do.state = state
    return do


WARN = {'level': 'warning', 'script': 'sync_programs.py', 'message': '3. sor: hiányzik a helyszín'}
ERROR = {'level': 'error', 'script': 'sync_equipment.py', 'message': 'Egyetlen eszköz sincs'}


def test_collect_groups_steps_and_skips_duplicates(run, monkeypatch, tmp_path):
    issue_file = tmp_path / 'x.jsonl'
    issue_file.write_text(json.dumps(WARN) + '\n' + json.dumps(WARN) + '\nnem json\n' + json.dumps(ERROR) + '\n',
                          encoding='utf-8')
    monkeypatch.setenv('SYNC_ISSUES_FILE', str(issue_file))
    monkeypatch.setenv('STEPS_JSON', json.dumps({'equipment': {'outcome': 'failure'}, 'calendar': {'outcome': 'failure'},
                                                 'install': {'outcome': 'failure'}, 'notices': {'outcome': 'success'},
                                                 'other': None}))
    issues = report.collect()
    assert issues == [('Programok', 'warning', WARN['message']), ('Eszközök', 'error', ERROR['message']),
                      ('Google Naptár', 'error', report.collect()[2][2]),
                      ('Csomagok telepítése', 'error', report.collect()[3][2])]
    assert 'váratlan hibával leállt' in issues[2][2]


def test_collect_without_inputs(monkeypatch):
    monkeypatch.setenv('STEPS_JSON', '{rossz')
    assert report.collect() == []


def test_report_cycle(run, smtp):
    run([WARN, ERROR])                                            # new → e-mail
    assert smtp.sent[-1]['Subject'] == '802 weboldal: 1 hiba és 1 figyelmeztetés a frissítésnél'
    body = smtp.sent[-1].get_content()
    assert '[HIBA, ÚJ] Egyetlen eszköz sincs' in body and 'Programok:' in body
    assert smtp.sent[-1]['To'] == 'admin@cserkesz.hu'
    run([WARN, ERROR], when=dt.datetime(2026, 11, 1, 11, 0))      # the same an hour later → nothing
    assert len(smtp.sent) == 1
    run([WARN], when=dt.datetime(2026, 11, 1, 12, 0))             # one solved → nothing, but forgotten
    assert len(smtp.sent) == 1
    run([WARN, ERROR], when=dt.datetime(2026, 11, 1, 13, 0))      # it is back → e-mail
    assert len(smtp.sent) == 2 and '[figyelmeztetés] 3. sor' in smtp.sent[-1].get_content()
    run([WARN, ERROR], when=dt.datetime(2026, 11, 2, 12, 0))      # 23 hours later → reminder
    assert len(smtp.sent) == 3
    run([], when=dt.datetime(2026, 11, 2, 13, 0))                 # all solved → one "minden rendben"
    assert smtp.sent[-1]['Subject'] == '802 weboldal: minden frissítés rendben'
    run([], when=dt.datetime(2026, 11, 2, 14, 0))
    assert len(smtp.sent) == 4


def test_report_only_warnings_subject_and_run_link(run, smtp, monkeypatch):
    monkeypatch.setenv('GITHUB_SERVER_URL', 'https://github.com')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'x/y')
    monkeypatch.setenv('GITHUB_RUN_ID', '42')
    run([WARN])
    assert smtp.sent[0]['Subject'] == '802 weboldal: 1 figyelmeztetés a frissítésnél'
    assert 'https://github.com/x/y/actions/runs/42' in smtp.sent[0].get_content()


def test_report_dry_run_and_no_smtp(run, capsys):
    run([WARN], dry=True)
    assert 'Tárgy: 802 weboldal' in capsys.readouterr().out and not run.state.exists()
    run([WARN])                                                   # no credentials: printed, not saved
    assert '(SMTP nélkül nem küldöm el)' in capsys.readouterr().out and not run.state.exists()


def test_report_send_error_is_not_saved(run, smtp, capsys):
    smtp.fail_send = OSError('hálózat')
    run([WARN])
    assert '::warning::A hibajelentő levél nem ment el' in capsys.readouterr().out
    assert not run.state.exists()


# ---------- check_site ----------

GOOD = '''<!DOCTYPE html><html><body>
<a href="#x">ugrás</a><div id="x"></div>
<!-- PROGRAMS:START -->
<article class="news-card" id="a" data-date="2026-10-11" data-end-date="2026-10-12"></article>
<!-- PROGRAMS:END -->
<div class="notice" data-from="2026-01-01" data-until="2026-02-01"></div>
<img src="kep.webp"><a href="https://kulso.hu">k</a><a href="mailto:a@x.hu">m</a>
</body></html>'''


def check(tmp_path, monkeypatch, html, name='programok.html', files=('kep.webp',)):
    monkeypatch.setattr(check_site, 'ROOT', str(tmp_path))
    for f in files:
        (tmp_path / f).write_bytes(b'x')
    page = tmp_path / name
    page.write_text(html, encoding='utf-8')
    return check_site.check_page(str(page))


def test_check_good_page(tmp_path, monkeypatch):
    assert check(tmp_path, monkeypatch, GOOD) == []


@pytest.mark.parametrize('change, problem', [
    (('<!-- PROGRAMS:END -->', ''), 'PROGRAMS generált rész hiányos'),
    (('id="x"', 'id="y"'), '#x hivatkozásnak nincs célpontja'),
    (('kep.webp', 'nincs.webp'), 'hiányzó fájlra mutató hivatkozás: nincs.webp'),
    (('data-date="2026-10-11"', 'data-date="2026-13-11"'), 'programkártya dátuma hibás'),
    (('data-end-date="2026-10-12"', 'data-end-date="2026-10-01"'), 'befejező dátuma hibás'),
    (('data-until="2026-02-01"', 'data-until="holnap"'), 'értesítő dátuma hibás (until: holnap)'),
    (('<div id="x"></div>', '<div id="x">#REF!</div>'), 'hibás érték került az oldalra: „#REF!”'),
    (('<div id="x"></div>', '<div id="x"> None </div>'), 'hibás érték került az oldalra: „None”'),
    (('class="news-card"', 'class="x-card"'), 'egyetlen program-kártya sincs'),
])
def test_check_finds_problems(tmp_path, monkeypatch, change, problem):
    problems = check(tmp_path, monkeypatch, GOOD.replace(*change))
    assert any(problem in p for p in problems), problems


def test_check_query_and_encoded_links(tmp_path, monkeypatch):
    html = GOOD.replace('kep.webp', 'Bel%C3%A9p%C3%A9si.pdf?v=3')
    assert check(tmp_path, monkeypatch, html, files=('Belépési.pdf',)) == []


def test_check_main_reports_warnings(tmp_path, monkeypatch, issues):
    check(tmp_path, monkeypatch, GOOD.replace('kep.webp', 'nincs.webp'))
    check_site.main()
    assert issues()[0]['message'].startswith('Oldalellenőrzés – programok.html: hiányzó fájlra')


# ---------- sync_footer ----------

def test_footer_writes_every_page_with_marker(site, monkeypatch, capsys):
    monkeypatch.setattr(footer.common, 'ROOT', str(site))
    monkeypatch.setenv('ADMIN_EMAIL', 'admin@cserkesz.hu')
    footer.main()
    html = (site / 'index.html').read_text(encoding='utf-8')
    assert 'jelezze az <a href="mailto:admin@cserkesz.hu">admin@cserkesz.hu</a> e-mail címen.' in html
    assert 'naptar.html' not in capsys.readouterr().out          # the redirect page has no footer
    footer.main()
    assert 'változatlan' in capsys.readouterr().out


def test_footer_article_and_escaping():
    assert 'jelezze a <a href="mailto:802@cserkesz.hu">' in footer.footer_line('802@cserkesz.hu')


@pytest.mark.parametrize('value', ['', 'nem cím', 'Név <a@b.hu>'])
def test_footer_invalid_address_keeps_pages(site, monkeypatch, issues, value):
    monkeypatch.setattr(footer.common, 'ROOT', str(site))
    monkeypatch.setenv('ADMIN_EMAIL', value)
    before = (site / 'index.html').read_text(encoding='utf-8')
    footer.main()
    assert (site / 'index.html').read_text(encoding='utf-8') == before
    assert 'ADMIN_EMAIL' in issues()[0]['message']
