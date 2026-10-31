import datetime as dt

import pytest

import sync_common as common
import sync_programs as programs
from conftest import csv_text

HEADER = ['Név', 'Kezdő dátum', 'Befejező dátum (ha több napos)', 'Kezdő idő', 'Befejező idő',
          'Időpont megjegyzése (pl. gyülekező)', 'Helyszín', 'Leírás', 'Kapcsolattartó 1 neve',
          'Kapcsolattartó 1 e-mail (kötelező)', 'Kapcsolattartó 1 telefonszám (opcionális)', 'Kapcsolattartó 2 neve',
          'Kapcsolattartó 2 e-mail', 'Kapcsolattartó 2 telefonszám', 'Facebook-esemény linkje',
          'Facebook-poszt linkje', 'Instagram-poszt linkje', 'Beszámoló', 'Képek', 'Megjelenjen?']
FUTURE = (dt.date.today() + dt.timedelta(days=30)).strftime('%Y.%m.%d.')


def program(**values):
    """One sheet row: an upcoming program with a valid contact, overridden by values."""
    row = dict.fromkeys(HEADER, '')
    row.update({'Név': 'Portya', 'Kezdő dátum': FUTURE, 'Helyszín': 'Erdő', 'Leírás': 'Gyertek!',
                'Kapcsolattartó 1 neve': 'Kiss Anna', 'Kapcsolattartó 1 e-mail (kötelező)': 'anna@cserkesz.hu',
                'Megjelenjen?': 'igen'})
    row.update({next(h for h in HEADER if h.startswith(k)): v for k, v in values.items()})
    return [row[h] for h in HEADER]


def parse(*rows, header=HEADER):
    return programs.parse_rows(csv_text([header, *rows]))


# ---------- parse_rows ----------

def test_valid_row_and_column_detection():
    rows, has_images = parse(program(Képek='okt_23', **{'Kapcsolattartó 1 telefon': '06301234567'}))
    assert has_images
    row = rows[0]
    assert row['name'] == 'Portya' and row['place'] == 'Erdő' and row['image_folder'] == 'okt_23'
    assert row['c1_phone'] == '06301234567' and row['label'] == '2. sor (Portya)'


def test_without_image_column():
    header = [h for h in HEADER if h != 'Képek']
    row = program()
    del row[HEADER.index('Képek')]
    rows, has_images = parse(row, header=header)
    assert rows and not has_images


@pytest.mark.parametrize('values, message', [
    ({'Kezdő dátum': ''}, 'hibás vagy hiányzó kezdő dátum'),
    ({'Kezdő dátum': '2026.02.30.'}, 'hibás vagy hiányzó kezdő dátum'),
    ({'Név': ''}, 'nincs megadva a program neve'),
    ({'Kapcsolattartó 1 neve': '', 'Kapcsolattartó 1 e-mail': ''}, 'nincs megadva kapcsolattartó'),
    ({'Kapcsolattartó 1 e-mail': ''}, 'nincs megadva e-mail címe'),
    ({'Kapcsolattartó 1 e-mail': 'anna.cserkesz.hu'}, 'nem tűnik érvényesnek'),
    ({'Kapcsolattartó 1 neve': '', 'Kapcsolattartó 2 neve': 'Béla', 'Kapcsolattartó 2 e-mail': 'b@x.hu'},
     '1. kapcsolattartónak nincs megadva a neve'),
    ({'Kapcsolattartó 2 neve': 'Nagy Béla'}, '2. kapcsolattartónak (Nagy Béla) nincs megadva e-mail'),
])
def test_rejected_rows(values, message, issues):
    rows, _ = parse(program(**values))
    assert rows == []
    assert message in issues()[0]['message']


def test_past_program_needs_no_contact(issues):
    rows, _ = parse(program(**{'Kezdő dátum': '2020.01.01.', 'Kapcsolattartó 1 neve': '',
                               'Kapcsolattartó 1 e-mail': ''}))
    assert len(rows) == 1 and issues() == []


def test_hidden_and_empty_rows_are_skipped(issues):
    rows, _ = parse(program(Megjelenjen='NEM'), [''] * len(HEADER), program(Név='Látszik'))
    assert [r['name'] for r in rows] == ['Látszik'] and issues() == []


def test_several_addresses_in_a_cell_use_the_first(issues):
    rows, _ = parse(program(**{'Kapcsolattartó 1 e-mail': 'anna@cserkesz.hu; bela@cserkesz.hu'}))
    assert rows[0]['c1_email'] == 'anna@cserkesz.hu'
    assert 'csak az elsőt használom' in issues()[0]['message']


def test_missing_place_and_description_is_a_warning_only(issues):
    rows, _ = parse(program(Helyszín='', Leírás=''))
    assert len(rows) == 1
    assert 'nincs megadva helyszín és leírás' in issues()[0]['message']


def test_times(issues):
    rows, _ = parse(program(Név='rossz', **{'Kezdő idő': '9.5', 'Befejező idő': '10:00'}),
                    program(Név='csak vége', **{'Kezdő idő': '', 'Befejező idő': '10:00'}),
                    program(Név='azonos', **{'Kezdő idő': '18:00', 'Befejező idő': '18.00'}),
                    program(Név='24 óra', **{'Kezdő idő': '24:00'}),
                    program(Név='éjszakai', **{'Kezdő idő': '9.30', 'Befejező idő': '1:05'}))
    assert {r['name']: (r['start_time'], r['end_time']) for r in rows} == {
        'rossz': (None, None), 'csak vége': (None, None), 'azonos': ('18:00', None), '24 óra': (None, None),
        'éjszakai': ('09:30', '01:05')}
    messages = ' '.join(i['message'] for i in issues())
    assert 'hibás kezdő idő ("9.5")' in messages
    assert 'van befejező idő, de nincs kezdő idő' in messages
    assert 'ugyanaz (18:00)' in messages
    assert 'hibás kezdő idő ("24:00")' in messages


def test_end_date_before_start_is_ignored(issues):
    rows, _ = parse(program(**{'Kezdő dátum': '2030.05.10.', 'Befejező dátum': '2030.05.01.'}))
    assert rows[0]['end'] is None
    assert 'a befejező dátum hibás' in issues()[0]['message']


def test_links_are_checked(issues):
    rows, _ = parse(program(**{'Facebook-esemény': 'javascript:alert(1)', 'Facebook-poszt': 'https://evil.com/x',
                               'Instagram': 'http://instagram.com/p/x'}),
                    program(**{'Facebook-esemény': 'https://fb.me/e', 'Facebook-poszt': 'https://m.facebook.com/p',
                               'Instagram': 'https://www.instagram.com/p/x/'}))
    assert (rows[0]['facebook'], rows[0]['fb_post'], rows[0]['ig_post']) == ('', '', '')
    assert (rows[1]['facebook'], rows[1]['fb_post'], rows[1]['ig_post']) == (
        'https://fb.me/e', 'https://m.facebook.com/p', 'https://www.instagram.com/p/x/')
    messages = [i['message'] for i in issues()]
    assert any('az Instagram-poszt linkje' in m for m in messages)
    assert any('a Facebook-poszt linkje' in m for m in messages)


def test_sheet_error_cell_is_empty(issues):
    rows, _ = parse(program(Helyszín='#ERROR!'))
    assert rows[0]['place'] == ''
    assert 'táblázathiba' in issues()[0]['message']


def test_placeholder_cell_is_empty(issues):
    rows, _ = parse(program(Helyszín='-'))
    assert rows[0]['place'] == ''
    assert 'Programok, "Helyszín" oszlop: helyőrző érték' in issues()[0]['message']


def test_sorting_by_date_then_time():
    rows, _ = parse(program(Név='C', **{'Kezdő dátum': '2030.01.02.'}),
                    program(Név='B', **{'Kezdő dátum': '2030.01.01.', 'Kezdő idő': '10:00'}),
                    program(Név='A', **{'Kezdő dátum': '2030.01.01.'}))
    assert [r['name'] for r in rows] == ['A', 'B', 'C']


def test_empty_sheet_fails(issues):
    with pytest.raises(SystemExit):
        programs.parse_rows('\n\n')


# ---------- small helpers ----------

@pytest.mark.parametrize('start, end, expected', [
    (dt.date(2026, 10, 11), None, '2026. október 11.'),
    (dt.date(2026, 10, 11), dt.date(2026, 10, 11), '2026. október 11.'),
    (dt.date(2026, 10, 11), dt.date(2026, 10, 9), '2026. október 11.'),      # end before start
    (dt.date(2026, 10, 11), dt.date(2026, 10, 13), '2026. október 11–13.'),
    (dt.date(2026, 10, 30), dt.date(2026, 11, 2), '2026. október 30. – november 2.'),
    (dt.date(2026, 12, 31), dt.date(2027, 1, 1), '2026. december 31. – 2027. január 1.'),
])
def test_display_date(start, end, expected):
    assert programs.display_date(start, end) == expected


@pytest.mark.parametrize('name, email, phone, expected', [
    ('Kiss Anna', 'a@x.hu', '', 'Kiss Anna, <a class="inline-link" href="mailto:a@x.hu">a@x.hu</a>'),
    ('', '', '06301234567', '<a class="inline-link" href="tel:+36301234567">+36 30 123 4567</a>'),
    ('Anna', '06301234567', '', 'Anna<br>\n            <a class="inline-link" href="tel:+36301234567">+36 30 123 4567</a>'),
    ('<b>Anna</b>', '', '', '&lt;b&gt;Anna&lt;/b&gt;'),
    ('Anna', 'a@x.hu?cc=b@y.hu', '', 'Anna, a@x.hu?cc=b@y.hu'),       # an old row's bad address: text, no link
])
def test_contact_html(name, email, phone, expected):
    assert programs.contact_html(name, email, phone) == expected


def test_card_ids_for_same_name_same_day():
    rows = [{'name': 'Mise', 'start': dt.date(2026, 1, 1)}] * 3 + [{'name': '🔥', 'start': dt.date(2026, 1, 2)}]
    assert programs.card_ids(rows) == ['mise-20260101', 'mise-20260101-2', 'mise-20260101-3', 'program-20260102']


# ---------- build_card ----------

def card(images_list=(), **values):
    rows, _ = parse(program(**values))
    row = rows[0]
    row['images'] = list(images_list)
    return programs.build_card(row, 'id-1')


def test_card_overnight_without_end_date_ends_next_day():
    html = card(**{'Kezdő dátum': '2030.01.10.', 'Kezdő idő': '22:00', 'Befejező idő': '02:00'})
    assert 'data-date="2030-01-10" data-end-date="2030-01-11"' in html
    assert '2030. január 10.</span>' in html        # the date label stays the start day


def test_card_overnight_with_explicit_end_date_is_not_shifted():
    html = card(**{'Kezdő dátum': '2030.12.31.', 'Befejező dátum': '2031.01.01.', 'Kezdő idő': '20:00',
                   'Befejező idő': '01:00'})
    assert 'data-end-date="2031-01-01"' in html


def test_card_single_day_has_no_end_attribute():
    assert 'data-end-date' not in card(**{'Kezdő idő': '10:00', 'Befejező idő': '12:00'})


def test_card_escapes_text_and_keeps_paragraphs():
    html = card(Név='<script>x</script>', Leírás='Első <b>bekezdés</b>\nsor\n\nMásodik', Beszámoló='Jó volt',
                **{'Facebook-esemény': 'https://www.facebook.com/events/1'})
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '<p>Első &lt;b&gt;bekezdés&lt;/b&gt;<br>sor</p>' in html
    assert '<span class="news-fb">Részletek a <a class="inline-link" href="https://www.facebook.com/events/1"' in html
    assert '<div class="news-text news-report" hidden>' in html


def test_card_facebook_link_without_description():
    html = card(Leírás='', **{'Facebook-esemény': 'https://www.facebook.com/events/1'})
    assert '<p><span class="news-fb">Részletek a' in html


def test_card_time_note_and_posts():
    html = card(**{'Kezdő idő': '17:45', 'Befejező idő': '19:00', 'Időpont megjegyzése': 'gyülekező',
                   'Facebook-poszt': 'https://www.facebook.com/p/1', 'Instagram': 'https://www.instagram.com/p/2'})
    assert '<strong>Időpont:</strong> 17:45–19:00 (gyülekező)' in html
    assert '<strong>Posztjaink:</strong> <a class="inline-link" href="https://www.facebook.com/p/1"' in html
    assert '>Facebook</a> · <a' in html and '>Instagram</a></p>' in html


def test_card_gallery_with_many_images_and_a_video():
    images = [{'thumb': f't{i}.webp', 'full': f'f{i}.webp', 'video': 'VID' if i == 2 else None} for i in range(3)]
    html = card(images_list=images)
    assert html.count('<img ') == 3
    assert 'data-video="VID"' in html and '– 3. videó' in html
    assert 'gallery-prev' in html and 'gallery-next' in html


def test_card_gallery_with_two_images_has_no_arrows():
    html = card(images_list=[{'thumb': 't.webp', 'full': 'f.webp', 'video': None}] * 2)
    assert 'gallery-prev' not in html


# ---------- main ----------

@pytest.fixture
def page(site, monkeypatch):
    monkeypatch.setattr(programs, 'PAGE', str(site / 'programok.html'))
    monkeypatch.setattr(programs, 'SNAPSHOT', str(site / 'data' / 'programs.csv'))
    import program_images
    monkeypatch.setattr(program_images, 'STATE', str(site / 'data' / 'program_images.json'))
    monkeypatch.setattr(program_images, 'DIR', str(site / 'images' / 'webp' / 'programok'))
    return site


def run_main(monkeypatch, path):
    monkeypatch.setattr('sys.argv', ['sync_programs.py', '--file', str(path)])
    programs.main()


def test_main_writes_cards_and_snapshot(page, tmp_path, monkeypatch, capsys, issues):
    source = tmp_path / 'p.csv'
    source.write_text(csv_text([HEADER, program(Név='Új portya'), program(Név='Új portya')]), encoding='utf-8')
    run_main(monkeypatch, source)
    html = (page / 'programok.html').read_text(encoding='utf-8')
    assert html.count('<article class="news-card"') == 2
    assert 'id="uj-portya-' in html and f'-{FUTURE[:4]}' in html and '-2"' in html
    assert (page / 'data' / 'programs.csv').read_text(encoding='utf-8') == source.read_text(encoding='utf-8')
    assert 'programok.html frissítve' in capsys.readouterr().out
    run_main(monkeypatch, source)     # the same again: unchanged
    assert 'programok.html változatlan' in capsys.readouterr().out


def test_main_without_valid_program_keeps_the_page(page, tmp_path, monkeypatch, issues):
    before = (page / 'programok.html').read_text(encoding='utf-8')
    source = tmp_path / 'p.csv'
    source.write_text(csv_text([HEADER, program(Megjelenjen='nem')]), encoding='utf-8')
    with pytest.raises(SystemExit):
        run_main(monkeypatch, source)
    assert (page / 'programok.html').read_text(encoding='utf-8') == before
    assert 'Egyetlen érvényes' in issues()[-1]['message']


def test_main_allow_empty(page, tmp_path, monkeypatch):
    monkeypatch.setenv('ALLOW_EMPTY', '1')
    source = tmp_path / 'p.csv'
    source.write_text(csv_text([HEADER, program(Megjelenjen='nem')]), encoding='utf-8')
    run_main(monkeypatch, source)
    assert '<article' not in (page / 'programok.html').read_text(encoding='utf-8').split('PROGRAMS:START')[1].split('PROGRAMS:END')[0]


def test_main_without_image_column_keeps_images(page, tmp_path, monkeypatch, issues):
    header = [h for h in HEADER if h != 'Képek']
    row = program()
    del row[HEADER.index('Képek')]
    source = tmp_path / 'p.csv'
    source.write_text(csv_text([header, row]), encoding='utf-8')
    run_main(monkeypatch, source)
    assert any('nincs "Képek" oszlop' in i['message'] for i in issues())


def test_missing_contact_email_rule():
    base = {'c1_name': 'A', 'c1_email': 'a@x.hu', 'c2_name': '', 'c2_email': ''}
    assert programs.missing_contact_email(base) == ''
    assert 'a(z) 2. kapcsolattartónak nincs megadva a neve' in programs.missing_contact_email({**base, 'c2_email': 'b@x.hu'})
    assert common.EMAIL is programs.EMAIL
