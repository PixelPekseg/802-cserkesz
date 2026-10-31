import datetime as dt

import pytest

import camp_reminder as camps
import troop_reminder as troops
from conftest import csv_text

TROOP_HEADER = ['Raj neve', 'Indulás éve', 'Jelenlegi osztály', 'Rajparancsnok 1 neve', 'Rajparancsnok 1 e-mail',
                'Rajparancsnok 1 telefon', 'Rajparancsnok 2 neve', 'Rajparancsnok 2 e-mail', 'Rajparancsnok 2 telefon',
                'Rajparancsnok 3 neve', 'Rajparancsnok 3 e-mail', 'Rajparancsnok 3 telefon', 'Megjelenjen?']
CAMP_HEADER = ['Név', 'Rövid leírás', 'Időpont', 'Helyszín', 'Főszervező 1 neve', 'Főszervező 1 e-mail',
               'Főszervező 1 telefon', 'Főszervező 2 neve', 'Főszervező 2 e-mail', 'Főszervező 2 telefon',
               'Főszervező 3 neve', 'Főszervező 3 e-mail', 'Főszervező 3 telefon', 'Megjelenjen?']


def troop(name, year, leader='', email='', phone='', visible='igen'):
    return [name, year, '', leader, email, phone, '', '', '', '', '', '', visible]


# ---------- troops ----------

@pytest.mark.parametrize('today, state, expected', [
    ('2026-09-14', {}, None),
    ('2026-09-15', {}, '2026-09-15'),
    ('2026-09-28', {}, '2026-09-15'),
    ('2026-09-29', {}, None),                                 # the 14-day window is over
    ('2026-09-20', {'2026-09-15': 'x'}, None),
    ('2026-10-15', {'2026-09-15': 'x'}, '2026-10-15'),
    ('2027-09-15', {'2026-09-15': 'x', '2026-10-15': 'x'}, '2027-09-15'),   # a new year
])
def test_troop_due(today, state, expected):
    assert troops.due_occasion(dt.date.fromisoformat(today), state) == expected


@pytest.mark.parametrize('rows, problem', [
    ([troop('Gomba', '2026', 'Kiss Anna', 'a@x.hu')], ''),
    ([troop('Gomba', '2026/27', 'Kiss Anna', '', '06301234567')], ''),          # phone only is enough
    ([troop('Régi', '2025', 'Anna', 'x@x.hu')], 'nincs olyan megjelenő raj'),
    ([troop('Gomba', '2026', 'Kiss Anna', 'a@x.hu', visible='nem')], 'nincs olyan megjelenő raj'),
    ([troop('Gomba', '2026', 'Kiss Anna')], 'a(z) Gomba sorában nincs rajparancsnok'),   # name only
    ([troop('', '2026', '', 'a@x.hu')], 'a(z) névtelen sorában'),
    ([troop('Gomba', 'kettőezer', 'Anna', 'x@x.hu')], 'nincs olyan megjelenő raj'),
])
def test_new_troop_problem(rows, problem):
    result = troops.new_troop_problem(csv_text([TROOP_HEADER, *rows]), dt.date(2026, 9, 15))
    assert (result == '') if not problem else (problem in result)


def test_troop_compose():
    subject, body = troops.compose(dt.date(2026, 9, 15), 'hiányzik X', again=False)
    assert subject == 'Hiányoznak az új rajparancsnokok a weboldalról'
    assert '2026/27-es tanévben' in body and 'hiányzik X.' in body and 'A weboldal „Csatlakozom” fülén' in body
    assert troops.compose(dt.date(2026, 10, 15), 'x', again=True)[0] == \
        'Emlékeztető: hiányoznak az új rajparancsnokok a weboldalról'


def test_troop_main(tmp_path, monkeypatch, smtp):
    data = tmp_path / 'r.csv'
    data.write_text(csv_text([TROOP_HEADER, troop('Régi', '2025', 'Anna', 'x@x.hu')]), encoding='utf-8')
    monkeypatch.setattr(troops, 'STATE', str(tmp_path / 'state.json'))
    monkeypatch.setattr('sys.argv', ['troop_reminder.py', '--today', '2026-10-16', '--file', str(data)])
    troops.main()
    assert smtp.sent[0]['To'].endswith('<802@cserkesz.hu>')
    assert smtp.sent[0]['Subject'].startswith('Emlékeztető:')          # October: the second one
    troops.main()
    assert len(smtp.sent) == 1


def test_troop_main_test_without_problem(tmp_path, monkeypatch, smtp):
    data = tmp_path / 'r.csv'
    data.write_text(csv_text([TROOP_HEADER, troop('Gomba', '2026', 'Anna', 'x@x.hu')]), encoding='utf-8')
    monkeypatch.setattr(troops, 'STATE', str(tmp_path / 'state.json'))
    monkeypatch.setenv('TEST_TROOP', 'true')
    monkeypatch.setattr('sys.argv', ['troop_reminder.py', '--today', '2026-12-01', '--file', str(data)])
    troops.main()
    assert 'nincs hiány (ez csak egy tesztlevél)' in smtp.sent[0].get_content()


# ---------- camps ----------

@pytest.mark.parametrize('today, state, expected', [
    ('2027-02-28', {}, None), ('2027-03-01', {}, '2027-03'), ('2027-03-14', {}, '2027-03'),
    ('2027-03-15', {}, None), ('2027-03-02', {'2027-03': 'x'}, None), ('2027-08-01', {}, '2027-08'),
    ('2027-09-01', {}, None), ('2027-12-01', {}, None),
])
def test_camp_due(today, state, expected):
    assert camps.due_month(dt.date.fromisoformat(today), state) == expected


@pytest.mark.parametrize('value, ok', [
    ('', False), (None, False), ('Hamarosan frissítjük!', False), ('hamarosan frissítjük', False), ('-', False),
    ('?', False), ('TBD', False), ('Később derül ki', False), ('Még nincs', False),
    ('2027. július 10–15.', True), ('Szegilong', True), ('Hamvas', True),
])
def test_camp_filled(value, ok):
    assert camps.filled(value) is ok


def camp(name, time='Júl. 1–5.', place='Erdő', organisers=(('A', 'a@x.hu', ''), ('B', '', '')), visible='igen'):
    cells = [name, 'leírás', time, place]
    for i in range(3):
        cells += list(organisers[i]) if i < len(organisers) else ['', '', '']
    return cells + [visible]


def test_camp_problems():
    text = csv_text([CAMP_HEADER,
                     camp('Jó'),
                     camp('Rossz', time='Hamarosan frissítjük!', place='', organisers=(('A', '', ''),)),
                     camp('Elérhetetlen', organisers=(('A', '', ''), ('B', '', ''))),
                     camp('Rejtett', time='', visible='nem')])
    problems = dict(camps.camp_problems(text))
    assert set(problems) == {'Rossz', 'Elérhetetlen'}
    assert problems['Rossz'][:2] == ['az időpont', 'a helyszín']
    assert 'most 1 van megadva' in problems['Rossz'][2]
    assert problems['Elérhetetlen'] == ['legalább egy elérhetőség (egy főszervező e-mail címe vagy telefonszáma)']


def test_camp_recipient(tmp_path, monkeypatch):
    leaders = tmp_path / 'leaders.csv'
    monkeypatch.setattr(camps.leaders, 'SNAPSHOT', str(leaders))
    assert camps.recipient() is None                                    # no snapshot yet
    leaders.write_text(csv_text([['Név', 'Szerep', 'E-mail', 'Megjelenjen?'],
                                 ['Kiss Anna', 'Csapatparancsnok', 'a@x.hu', 'igen'],
                                 ['Rossz Cím', 'Tábor és programok', 'nem-cim', 'igen'],
                                 ['Bedő Gergely', 'Tábor és programok', 'bedo@x.hu, masik@x.hu', 'igen']]),
                       encoding='utf-8')
    assert camps.recipient() == ('Bedő Gergely', 'bedo@x.hu')


def test_camp_compose_greeting():
    _, body = camps.compose(('Bedő Gergely', 'b@x.hu'), [('Nagytábor', ['az időpont', 'a helyszín'])])
    assert body.startswith('Kedves Gergely!') and '- Nagytábor: hiányzik az időpont, a helyszín' in body
    assert camps.compose(None, [('X', ['y'])])[1].startswith('Sziasztok!')


def test_camp_main_falls_back_to_team_address(tmp_path, monkeypatch, smtp, issues):
    data = tmp_path / 't.csv'
    data.write_text(csv_text([CAMP_HEADER, camp('Nagytábor', place='')]), encoding='utf-8')
    monkeypatch.setattr(camps, 'STATE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(camps.leaders, 'SNAPSHOT', str(tmp_path / 'nincs.csv'))
    monkeypatch.setattr('sys.argv', ['camp_reminder.py', '--today', '2027-04-02', '--file', str(data)])
    camps.main()
    assert smtp.sent[0]['To'].endswith('<802@cserkesz.hu>')
    assert 'Nem találtam a Csapatvezetés lapon' in issues()[0]['message']


def test_camp_main_test_without_problems(tmp_path, monkeypatch, smtp):
    data = tmp_path / 't.csv'
    data.write_text(csv_text([CAMP_HEADER, camp('Jó')]), encoding='utf-8')
    monkeypatch.setattr(camps, 'STATE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(camps.leaders, 'SNAPSHOT', str(tmp_path / 'nincs.csv'))
    monkeypatch.setenv('TEST_CAMP', '1')
    monkeypatch.setenv('TEST_CAMP_TO', 't@x.hu')
    monkeypatch.setattr('sys.argv', ['camp_reminder.py', '--today', '2027-11-01', '--file', str(data)])
    camps.main()
    assert smtp.sent[0]['To'] == 't@x.hu' and '(teszt): hiányzik semmi' in smtp.sent[0].get_content()
