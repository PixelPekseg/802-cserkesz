#!/usr/bin/env python3
"""Checks the generated pages after the hourly sync, before they are saved.

Every problem is reported as a warning (common.warn), so it ends up in the e-mail of
tools/report_issues.py. It does not change anything. Checks:
  - every page parses as HTML, and its generated parts (<!-- X:START … --> … <!-- X:END -->) are complete;
  - no sheet error value (#ERROR!, #REF! …), "None", "undefined" or "nan" got onto a page;
  - every link to a file of the site (pages, images, PDFs, styles, scripts) points to an existing file,
    and every #anchor link inside a page has its target;
  - the program cards have valid ISO dates (data-date / data-end-date, the end not before the start);
  - the notices' dates are valid;
  - there is at least one program card, camp card, troop card and leader card.

Usage:
    python tools/check_site.py
"""
import datetime as dt
import glob
import html.parser
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402

ROOT = common.ROOT
BAD_TEXT = re.compile(r'#(?:ERROR!|REF!|NAME\?|VALUE!|N/A|DIV/0!|NUM!|NULL!)|>\s*(?:None|undefined|nan|NaN)\s*<')
LINK = re.compile(r'(?:href|src|data-full|data-src)="([^"]+)"')
REQUIRED_PARTS = {
    'programok.html': ('news-card', 'program'),
    'tabor.html': ('camp-card', 'tábor'),
    'csatlakozom.html': ('grade-card', 'raj'),
    'index.html': ('person-card', 'vezető'),
}


class Parser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == 'id' and value:
                self.ids.add(value)


def iso_date(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def check_page(path):
    name = os.path.basename(path)
    text = open(path, encoding='utf-8').read()
    problems = []

    parser = Parser()
    try:
        parser.feed(text)
    except Exception as error:   # html.parser is lenient; anything raised here is a real problem
        problems.append(f'nem olvasható HTML-ként ({error})')

    starts = re.findall(r'<!-- ([A-Z_]+):START', text)
    ends = re.findall(r'<!-- ([A-Z_]+):END -->', text)
    for marker in sorted(set(starts) ^ set(ends)):
        problems.append(f'a(z) {marker} generált rész hiányos (hiányzik a kezdő vagy a záró jelölő)')

    for match in BAD_TEXT.finditer(text):
        problems.append(f'hibás érték került az oldalra: „{match.group(0).strip("<> ")}”')

    for link in LINK.findall(text):
        if re.match(r'(?:https?:|mailto:|tel:|webcal:|data:|//|javascript:)', link):
            continue
        target, _, anchor = link.partition('#')
        target = urllib.parse.unquote(target.split('?')[0])
        if target and not os.path.exists(os.path.join(ROOT, target)):
            problems.append(f'hiányzó fájlra mutató hivatkozás: {link}')
        elif not target and anchor and anchor not in parser.ids:
            problems.append(f'a(z) #{anchor} hivatkozásnak nincs célpontja az oldalon')

    for match in re.finditer(r'<article class="news-card" id="([^"]*)"([^>]*)>', text):
        card, attrs = match.groups()
        start = iso_date((re.search(r'data-date="([^"]*)"', attrs) or [None, None])[1])
        end_value = (re.search(r'data-end-date="([^"]*)"', attrs) or [None, None])[1]
        end = iso_date(end_value) if end_value else start
        if not start:
            problems.append(f'a(z) {card} programkártya dátuma hibás')
        elif not end or end < start:
            problems.append(f'a(z) {card} programkártya befejező dátuma hibás')

    for attrs in re.findall(r'<div class="notice"([^>]*)>', text):
        for key, value in re.findall(r'data-(from|until)="([^"]*)"', attrs):
            if not iso_date(value):
                problems.append(f'egy értesítő dátuma hibás ({key}: {value})')

    if name in REQUIRED_PARTS:
        css_class, label = REQUIRED_PARTS[name]
        if not re.search(rf'class="(?:[^"]* )?{css_class}[ "]', text):
            problems.append(f'egyetlen {label}-kártya sincs az oldalon')
    return [f'{name}: {problem}' for problem in dict.fromkeys(problems)]


def main():
    pages = sorted(glob.glob(os.path.join(ROOT, '*.html')))
    problems = [problem for page in pages for problem in check_page(page)]
    for problem in problems:
        common.warn(f'Oldalellenőrzés – {problem}')
    print(f'{len(pages)} oldal ellenőrizve, {len(problems)} probléma.')


if __name__ == '__main__':
    main()
