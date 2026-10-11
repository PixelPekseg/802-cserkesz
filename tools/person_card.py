"""Személykártya (fotó/monogram, név, szerep, e-mail; kattintásra felugró ablak a rejtett
.person-bio tartalmával) – közös a sync_vezetok.py és a sync_eszkozok.py számára.
A felugró ablakot a script.js (.person-card.has-bio) kezeli."""
import html

import sync_common as common
from drive_photos import initials


def esc(text):
    return html.escape(text, quote=True)


def build_card(row, photo, indent):
    """row: name, role, intro, why (soronként egy pont), emails (lista), phone."""
    i = indent
    emails = row['emails']
    lines = [
        f'{i}<div class="person-card has-bio">',
        f'{i}  <div class="person-photo" data-initials="{esc(initials(row["name"]))}">',
    ]
    if photo:
        lines.append(f'{i}    <img src="{photo}" alt="{esc(row["name"])}" data-optional>')
    lines += [
        f'{i}  </div>',
        f'{i}  <h3>{esc(row["name"])}</h3>',
        f'{i}  <p class="person-role">{esc(row["role"])}</p>',
    ]
    if emails:
        user, domain = emails[0].split('@', 1)
        lines.append(f'{i}  <a class="person-email" href="mailto:{esc(emails[0])}">{esc(user)}@<wbr>{esc(domain)}</a>')
    lines += [
        f'{i}  <div class="person-bio" hidden>',
        f'{i}    <p class="person-bio-role">{esc(row.get("intro") or row["role"])}</p>',
    ]
    points = [line.strip() for line in row.get('why', '').splitlines() if line.strip()]
    if points:
        lines.append(f'{i}    <p class="person-bio-title">Miért keresd?</p>')
        lines.append(f'{i}    <ul class="person-bio-list">')
        lines += [f'{i}      <li>{esc(point)}</li>' for point in points]
        lines.append(f'{i}    </ul>')
    contacts = [f'<a class="person-email" href="mailto:{esc(email)}">{esc(email)}</a>' for email in emails]
    if row.get('phone'):
        contacts += common.contact_lines('', row['phone'])
    if contacts:
        lines.append(f'{i}    <ul class="person-bio-contact">')
        lines += [f'{i}      <li>{contact}</li>' for contact in contacts]
        lines.append(f'{i}    </ul>')
    lines += [f'{i}  </div>', f'{i}</div>']
    return '\n'.join(lines)
