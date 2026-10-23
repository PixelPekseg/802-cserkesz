#!/usr/bin/env python3
"""Builds the gallery of galeria.html from every photo and video of the site.

Usage:
    python tools/sync_gallery.py

Rewrites the part of galeria.html between <!-- GALLERY:START --> and <!-- GALLERY:END -->.
Sections:
    Programjaink      the programs' images and videos (images/webp/programok/, they come from Drive),
                      per folder, with the program's name, the latest program first
                      (based on data/programs.csv and data/program_images.json)
    Tábor             images/webp/tabor/
    Csapatotthonunk   images/webp/csapatotthon/
    Csapatunk         images/webp/fooldal/ and images/webp/rolunk/
Left out: the leaders' portraits (kozos/team), logos, pictograms, the poster and QR code of the
Támogass page. Alt texts come from the pages' <img> elements (when present). Where a thumbnail
exists (thumb/), the gallery shows it and the lightbox shows the large version. Videos are played
by the Drive player (on click, in the lightbox). Uses the Python standard library only.
"""
import glob
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common
import sync_programs as programs
from program_images import STATE as PROGRAM_STATE, folder_parts, on_disk

PAGE = os.path.join(common.ROOT, 'galeria.html')
WEBP = 'images/webp'
STATIC_SECTIONS = [
    ('Tábor', ['tabor']),
    ('Csapatotthonunk', ['csapatotthon']),
    ('Csapatunk', ['fooldal', 'rolunk']),
]


def alt_texts():
    """{image path: alt text} from the pages' <img> elements, in order of appearance."""
    alts = {}
    for page in sorted(glob.glob(os.path.join(common.ROOT, '*.html'))):
        if os.path.basename(page) == 'galeria.html':
            continue
        text = open(page, encoding='utf-8').read()
        for tag in re.findall(r'<img\b[^>]*>', text):
            alt = re.search(r'\balt="([^"]*)"', tag)
            for attr in ('data-full', 'src'):
                src = re.search(rf'\b{attr}="([^"]+)"', tag)
                if src and alt and alt.group(1).strip():
                    alts.setdefault(html.unescape(src.group(1)), html.unescape(alt.group(1)).strip())
    return alts


def figure(thumb, full, alt, video=None):
    attrs = f' data-video="{html.escape(video, quote=True)}"' if video else ''
    return (f'          <img src="{thumb}" data-full="{full}"{attrs} '
            f'alt="{html.escape(alt, quote=True)}" loading="lazy">')


def static_items(folders, title, alts):
    items, order = [], list(alts)
    for folder in folders:
        files = sorted(glob.glob(os.path.join(common.ROOT, WEBP, folder, '*.webp')))
        rel = [f'{WEBP}/{folder}/{os.path.basename(f)}' for f in files]
        # in the order they appear on the pages, the rest after them
        rel.sort(key=lambda p: (order.index(p) if p in order else len(order), p))
        for full in rel:
            thumb = f'{WEBP}/{folder}/thumb/{os.path.basename(full)}'
            if not os.path.exists(os.path.join(common.ROOT, thumb)):
                thumb = full
            items.append((thumb, full, alts.get(full) or alts.get(thumb) or title, None))
    for n, (thumb, full, alt, video) in enumerate(items, start=1):
        if alt == title:
            items[n - 1] = (thumb, full, f'{title} – {n}. kép', video)
    return items


def program_groups():
    """[(title, date text, items)], the latest program first."""
    snapshot = os.path.join(common.ROOT, 'data', 'programs.csv')
    if not os.path.exists(snapshot):
        return []
    try:
        state = json.load(open(PROGRAM_STATE, encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    rows = programs.parse_rows(open(snapshot, encoding='utf-8').read())
    folders = {}
    for row in rows:
        _, slug = folder_parts(row['image_folder'])
        if slug:
            folders.setdefault(slug, []).append(row)
    groups = []
    for slug, members in folders.items():
        items = on_disk(state, slug)
        if not items:
            continue
        names = list(dict.fromkeys(r['name'] for r in members))
        latest = max(members, key=lambda r: r['start'])
        title = ', '.join(names)
        figures = [(i['thumb'], i['full'],
                    f'{title} – {n}. {"videó" if i["video"] else "kép"}', i['video'])
                   for n, i in enumerate(items, start=1)]
        groups.append((latest['start'], title, programs.display_date(latest['start'], latest['end']), figures))
    groups.sort(key=lambda g: g[0], reverse=True)
    return [(title, date, figures) for _, title, date, figures in groups]


def build():
    alts = alt_texts()
    lines = []
    groups = program_groups()
    if groups:
        lines.append('      <section class="gallery-section" id="galeria-programok">')
        lines.append('        <h2>Programjaink</h2>')
        for title, date, figures in groups:
            lines.append(f'        <h3 class="gallery-subtitle">{html.escape(title)} '
                         f'<span class="gallery-date">{html.escape(date)}</span></h3>')
            lines.append('        <div class="site-gallery">')
            lines += [figure(*f) for f in figures]
            lines.append('        </div>')
        lines.append('      </section>')
    for title, folders in STATIC_SECTIONS:
        items = static_items(folders, title, alts)
        if not items:
            continue
        lines.append(f'      <section class="gallery-section" id="galeria-{programs.slugify(title)}">')
        lines.append(f'        <h2>{html.escape(title)}</h2>')
        lines.append('        <div class="site-gallery">')
        lines += [figure(*f) for f in items]
        lines.append('        </div>')
        lines.append('      </section>')
    return '\n'.join(lines)


def main():
    body = build()
    changed = common.replace_block(PAGE, 'GALLERY', body, ' ' * 6)
    count = body.count('<img ')
    print(f'{count} kép/videó a galériában; galeria.html {"frissítve" if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
