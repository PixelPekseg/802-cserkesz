"""The smaller sheet → page syncs: camps, troops, notices, counters, leaders, equipment, person cards."""
import datetime as dt

import pytest

import person_card
import sync_camps
import sync_counters
import sync_equipment
import sync_leaders
import sync_notices
import sync_troops
from conftest import block, csv_text, run_script
from test_seasonal_reminders import CAMP_HEADER, TROOP_HEADER, camp, troop


def write(tmp_path, name, rows):
    path = tmp_path / name
    path.write_text(csv_text(rows), encoding='utf-8')
    return path


# ---------- camps ----------

def test_camps_cards_placeholders_and_snapshot(paths, tmp_path, monkeypatch, capsys):
    source = write(tmp_path, 'c.csv', [CAMP_HEADER, camp('Nagy<tábor>', time='', place='Szegilong',
                                                         organisers=(('A', 'a@x.hu', '06301234567'),)),
                                       camp('Rejtett', visible='nem'), camp('')])
    run_script(sync_camps, monkeypatch, '--file', source)
    html = block(paths / 'tabor.html', 'CAMPS')
    assert html.count('class="camp-card"') == 1 and 'Nagy&lt;tábor&gt;' in html
    assert 'Hamarosan frissítjük!' in html and 'Szegilong' in html
    assert 'href="tel:+36301234567"' in html and 'Főszervezők' in html
    assert (paths / 'data' / 'camps.csv').exists()
    assert 'nincs megadva a tábor neve' in capsys.readouterr().out


def test_camps_without_visible_camp_fails(paths, tmp_path, monkeypatch, issues):
    before = (paths / 'tabor.html').read_text(encoding='utf-8')
    with pytest.raises(SystemExit):
        run_script(sync_camps, monkeypatch, '--file', write(tmp_path, 'c.csv', [CAMP_HEADER, camp('X', visible='nem')]))
    assert (paths / 'tabor.html').read_text(encoding='utf-8') == before


def test_camp_card_without_organisers():
    row = dict(zip(sync_camps.COLUMNS, ['Tábor', '', 'jún.', 'Erdő'] + [''] * 10))
    assert 'Főszervezők' not in sync_camps.build_card(row) and 'camp-card-lead' not in sync_camps.build_card(row)


# ---------- troops ----------

def test_troops_grades_hidden_and_cub_camp_contacts(paths, tmp_path, monkeypatch, issues):
    year = dt.date.today().year if dt.date.today().month >= 9 else dt.date.today().year - 1
    rows = [TROOP_HEADER, troop('Új', str(year), 'Kiss Anna', 'a@x.hu'), troop('Jövő', str(year + 1), 'B', 'b@x.hu'),
            troop('Régi', str(year - 6), 'C', 'c@x.hu'), troop('Vezető nélkül', str(year - 1)),
            troop('Rossz év', 'kétezer', 'D', 'd@x.hu'), troop('', str(year), 'E', 'e@x.hu'),
            troop('Rejtett', str(year), 'F', 'f@x.hu', visible='nem')]
    run_script(sync_troops, monkeypatch, '--file', write(tmp_path, 't.csv', rows))
    html = block(paths / 'csatlakozom.html', 'TROOPS')
    assert html.index('Jövő') < html.index('>Új<') < html.index('Vezető nélkül') < html.index('Régi')  # youngest first
    assert f'data-school-year="{year + 1}" hidden' in html and f'data-school-year="{year - 6}" hidden' in html
    assert '<h3>4. osztály</h3>' in html and 'Rajparancsnokok: hamarosan frissítjük!' in html
    finance = block(paths / 'penzugyek.html', 'CUB_CAMP_CONTACTS')
    assert 'Kiss Anna' in finance and finance.count('class="fee-troop"') == 4
    messages = ' '.join(i['message'] for i in issues())
    assert 'hibás indulási év ("kétezer")' in messages and 'nincs megadva a raj neve' in messages
    assert 'Vezető nélkül): nincs megadva rajparancsnok' in messages


def test_troops_school_year_turns_on_september_1():
    assert sync_troops.school_year(dt.date(2026, 8, 31)) == 2025
    assert sync_troops.school_year(dt.date(2026, 9, 1)) == 2026


def test_troops_empty_fails(paths, tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        run_script(sync_troops, monkeypatch, '--file', write(tmp_path, 't.csv', [TROOP_HEADER, troop('X', 'rossz')]))


# ---------- notices ----------

NOTICE_HEADER = ['Cím', 'Mettől', 'Meddig', 'Határidő', 'Üzenet', 'Megjelenjen?']


def test_notices(paths, tmp_path, monkeypatch, issues):
    far = (dt.date.today() + dt.timedelta(days=60)).strftime('%Y.%m.%d.')
    rows = [NOTICE_HEADER,
            ['Tagdíj', '', '', far, 'Utald át <b>most</b>!', 'igen'],
            ['', '', '', '', 'Csak üzenet', 'igen'],
            ['Lejárt', '2020.01.01.', '2020.02.01.', '', 'régi', 'igen'],
            ['Fordított', '2030.05.10.', '2030.05.01.', '', 'x', 'igen'],
            ['Rossz', 'tegnap', '', '2030.13.01.', 'y', 'igen'],
            ['', '', '', '', '', 'igen'],
            ['Rejtett', '', '', '', 'z', 'nem']]
    run_script(sync_notices, monkeypatch, '--file', write(tmp_path, 'n.csv', rows))
    html = block(paths / 'index.html', 'NOTICES')
    assert html.count('class="notice"') == 3
    assert 'Utald át &lt;b&gt;most&lt;/b&gt;!' in html and 'Határidő:' in html
    assert '<strong class="notice-title"></strong>' not in html          # no empty bold title
    assert block(paths / 'tabor.html', 'NOTICES') == html                 # the same on every page
    messages = ' '.join(i['message'] for i in issues())
    assert 'így soha nem jelenne meg' in messages and 'nincs se cím, se üzenet' in messages
    assert '"Mettől" nem értelmezhető dátum ("tegnap")' in messages


def test_notice_id_changes_with_the_text():
    a = sync_notices.build_notice({'title': 'T', 'message': 'M'}, None, None, None)
    b = sync_notices.build_notice({'title': 'T', 'message': 'M2'}, None, None, None)
    assert a.split('data-id="')[1][:10] != b.split('data-id="')[1][:10]


def test_no_notice_makes_an_empty_bar(paths, tmp_path, monkeypatch):
    run_script(sync_notices, monkeypatch, '--file', write(tmp_path, 'n.csv', [NOTICE_HEADER, ['X', '', '', '', 'y', 'nem']]))
    assert '<div class="notice-bar" id="noticeBar"></div>' in block(paths / 'index.html', 'NOTICES')


# ---------- counters ----------

@pytest.mark.parametrize('number, expected', [
    ('1200', 1200), ('1 200', 1200), ('1.200', 1200), ('1,200', 1200), ('1 200', 1200), ('45', 45),
    ('4.5', None), ('-3', None), ('', None), ('411 fő', None), ('sok', None), ('12 34', None),
])
def test_counters_number_formats(paths, tmp_path, monkeypatch, number, expected):
    rows = [['Felirat', 'Szám', 'Megjelenjen?'], ['Tag', number, 'igen'], ['Raj', '7', 'igen']]
    run_script(sync_counters, monkeypatch, '--file', write(tmp_path, 'c.csv', rows))
    html = block(paths / 'index.html', 'COUNTERS')
    if expected is None:
        assert 'Tag' not in html
    else:
        assert f'data-count="{expected}"' in html


def test_counters_grouping_and_failures(paths, tmp_path, monkeypatch, issues):
    assert sync_counters.format_number(1234567) == '1&nbsp;234&nbsp;567'
    rows = [['Felirat', 'Szám', 'Megjelenjen?'], ['', '5', 'igen'], ['Tag', '5', 'nem']]
    with pytest.raises(SystemExit):
        run_script(sync_counters, monkeypatch, '--file', write(tmp_path, 'c.csv', rows))
    assert 'nincs megadva a felirat' in issues()[0]['message']


# ---------- person cards ----------

def test_person_card_variants():
    html = person_card.build_card({'name': 'Kiss Anna', 'role': 'Pénzügyek', 'intro': 'Első sor\n\nMásodik <b>',
                                   'email': 'anna@x.hu', 'phone': '06301234567'}, 'kep.webp', '  ')
    assert '<img src="kep.webp" alt="Kiss Anna" data-optional>' in html
    assert 'anna@<wbr>x.hu' in html and 'href="tel:+36301234567">+36 30 123 4567<' in html
    assert '<p class="person-bio-text">Első sor<br>Második &lt;b&gt;</p>' in html
    plain = person_card.build_card({'name': 'Béla', 'role': 'X', 'email': '', 'phone': '112'}, None, '')
    assert 'data-initials="B"' in plain and '<img' not in plain and '<span class="person-phone">112</span>' in plain
    assert 'person-bio-contact' in plain


# ---------- leaders ----------

LEADER_HEADER = ['Név', 'Szerep (a kártyán)', 'Bemutatkozás', 'E-mail', 'Telefon', 'Fotó', 'Megjelenjen?']


def test_leaders(paths, tmp_path, monkeypatch, issues, capsys):
    rows = [LEADER_HEADER,
            ['Cseri-Holzman Lili', 'Csapatparancsnok', 'Szia', '802@cserkesz.hu, lili@x.hu', '', '', 'igen'],
            ['Grébel Hanna', 'Csapatotthon', '', 'grebel.hanna@cserkesz.hu', '+36303306130', 'hanna.jpg', 'igen'],
            ['Grebel Hanna', 'Pénzügyek', '', 'nem-cim', '', 'x.jpg', 'igen'],          # same name without accents
            ['', 'Szerep név nélkül', '', '', '', '', 'igen'],
            ['Rejtett', 'X', '', '', '', '', 'nem']]
    run_script(sync_leaders, monkeypatch, '--file', write(tmp_path, 'v.csv', rows))
    index = block(paths / 'index.html', 'LEADERS')
    assert index.count('class="person-card') == 3 and 'lili@x.hu' not in index
    assert 'Grébel Hanna' in block(paths / 'csapatotthon.html', 'LEADERS_HOME')
    assert 'Grebel Hanna' in block(paths / 'penzugyek.html', 'LEADERS_FINANCE')
    messages = ' '.join(i['message'] for i in issues())
    for part in ('csak az elsőt használom (802@cserkesz.hu)', 'nem tűnik érvényesnek', 'egy korábbi sorral egyezik',
                 'hiányzik a név vagy a szerep', 'GOOGLE_API_KEY'):
        assert part in messages


def test_leaders_without_home_or_finance_role(paths, tmp_path, monkeypatch, issues):
    run_script(sync_leaders, monkeypatch, '--file', write(tmp_path, 'v.csv', [LEADER_HEADER,
                                                                              ['A B', 'Csapatparancsnok', '', '', '', '', '']]))
    messages = ' '.join(i['message'] for i in issues())
    assert 'nincs "Csapatotthon"' in messages and 'nincs "Pénzügy"' in messages


def test_leaders_empty_fails(paths, tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        run_script(sync_leaders, monkeypatch, '--file', write(tmp_path, 'v.csv', [LEADER_HEADER, ['A', 'B', '', '', '', '', 'nem']]))


# ---------- equipment ----------

ITEM_HEADER = ['Eszköz', 'Darabszám', 'Megjegyzés (pl. méret)', 'Megjelenjen?']
CONTACT_HEADER = ['Név', 'Szerep', 'E-mail', 'Telefon', 'Fájlnév', 'Megjelenjen?']


def test_equipment(paths, tmp_path, monkeypatch, issues):
    items = write(tmp_path, 'e.csv', [ITEM_HEADER, ['Sörsátor', '2 db', '6×3 m', 'igen'], ['Sörpad', '30', '', ''],
                                      ['Sátor', 'sok', '', 'igen'], ['', '3', '', 'igen'], ['Rejtett', '1', '', 'nem']])
    contacts = write(tmp_path, 'k.csv', [CONTACT_HEADER, ['Korzenszky Gergő', '', 'a@x.hu; b@x.hu', '', '', 'igen'],
                                         ['Rossz', 'x', 'nem-cim', '', '', ''], ['', 'x', '', '', '', '']])
    run_script(sync_equipment, monkeypatch, '--file', items, '--contact-file', contacts)
    html = block(paths / 'eszkozok.html', 'EQUIPMENT')
    assert '<span class="gear-count">2 db</span>' in html and '6×3 m' in html and 'Sátor' in html
    assert html.count('gear-count') == 2                       # "sok" is dropped, the item stays
    cards = block(paths / 'eszkozok.html', 'EQUIPMENT_CONTACT')
    assert 'Kapcsolattartó' in cards and 'a@<wbr>x.hu' in cards and 'b@x.hu' not in cards
    messages = ' '.join(i['message'] for i in issues())
    assert 'nem egész szám ("sok")' in messages and 'nincs megadva az eszköz neve' in messages
    assert 'nem tűnik érvényesnek, kihagyva: "nem-cim"' in messages and 'nincs megadva a név' in messages


def test_equipment_without_contacts_uses_team_address(paths, tmp_path, monkeypatch, issues):
    items = write(tmp_path, 'e.csv', [ITEM_HEADER, ['Sátor', '1', '', 'igen']])
    contacts = write(tmp_path, 'k.csv', [CONTACT_HEADER, ['X', '', '', '', '', 'nem']])
    run_script(sync_equipment, monkeypatch, '--file', items, '--contact-file', contacts)
    assert 'mailto:802@cserkesz.hu' in block(paths / 'eszkozok.html', 'EQUIPMENT_CONTACT')
    assert 'a csapat közös e-mail címe' in issues()[-1]['message']


def test_equipment_empty_list_keeps_the_page(paths, tmp_path, monkeypatch, issues):
    before = (paths / 'eszkozok.html').read_text(encoding='utf-8')
    items = write(tmp_path, 'e.csv', [ITEM_HEADER])
    contacts = write(tmp_path, 'k.csv', [CONTACT_HEADER, ['X', '', '', '', '', '']])
    with pytest.raises(SystemExit):
        run_script(sync_equipment, monkeypatch, '--file', items, '--contact-file', contacts)
    assert (paths / 'eszkozok.html').read_text(encoding='utf-8') == before
