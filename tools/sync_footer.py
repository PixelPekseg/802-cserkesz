#!/usr/bin/env python3
"""Writes the "report a problem" line of the footer on every page from the ADMIN_EMAIL secret.

The address is the same as the one the reminder e-mails are sent from, so changing the GitHub
Secret updates the footer on the next run. Rewrites the part between
    <!-- ADMIN_CONTACT:START ... -->  ...  <!-- ADMIN_CONTACT:END -->
of every page that has it. Without a valid ADMIN_EMAIL the pages stay unchanged (a warning).

Usage:
    ADMIN_EMAIL=nev@cserkesz.hu python tools/sync_footer.py
"""
import glob
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_common as common  # noqa: E402

EMAIL = re.compile(r'[^@\s<>"]+@[^@\s<>"]+\.[^@\s<>"]+')


def footer_line(address):
    # Hungarian article: "az admin@…", "a 802@…" ("1" and "5" are read with a vowel: egy, öt)
    article = 'az' if address[:1].lower() in 'aáeéiíoóöőuúüű15' else 'a'
    safe = html.escape(address, quote=True)
    return (f'      <p class="footer-report">Ha problémát tapasztal, kérjük, jelezze {article} '
            f'<a href="mailto:{safe}">{safe}</a> e-mail címen.</p>')


def main():
    address = os.environ.get('ADMIN_EMAIL', '').strip()
    if not EMAIL.fullmatch(address):
        common.warn('Nincs beállítva (vagy nem e-mail cím) az ADMIN_EMAIL titok, a lábléc hibabejelentő '
                    'sora változatlan marad.')
        return
    body = footer_line(address)
    changed = []
    for path in sorted(glob.glob(os.path.join(common.ROOT, '*.html'))):
        with open(path, encoding='utf-8') as handle:
            if 'ADMIN_CONTACT:START' not in handle.read():
                continue
        if common.replace_block(path, 'ADMIN_CONTACT', body, ' ' * 6):
            changed.append(os.path.basename(path))
    print(f'Lábléc hibabejelentő sora: {"frissítve: " + ", ".join(changed) if changed else "változatlan"}.')


if __name__ == '__main__':
    main()
