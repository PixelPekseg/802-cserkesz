"""Személykártya (fotó/monogram, név, szerep, e-mail; kattintásra felugró ablak a rejtett
.person-bio tartalmával) – közös a sync_vezetok.py és a sync_eszkozok.py számára.
A felugró ablakot a script.js (.person-card.has-bio) kezeli."""
import html
import re

import sync_common as common
from drive_photos import initials


def esc(text):
    return html.escape(text, quote=True)


def build_card(row, photo, indent):
    """row: name, role, intro (rövid bemutatkozó szöveg, opcionális), email, phone (opcionális;
    ha meg van adva, a kártyán az e-mail alatt és a felugró ablakban is megjelenik).
    A felugró ablak fejlécében a név és a szerep áll (person-bio-role), alatta a bemutatkozás,
    majd az elérhetőségek."""
    i = indent
    email = row.get('email', '')
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
    if email:
        user, domain = email.split('@', 1)
        lines.append(f'{i}  <a class="person-email" href="mailto:{esc(email)}">{esc(user)}@<wbr>{esc(domain)}</a>')
    # telefonszám a kártyán is, az e-mail alatt (nem csak a felugró ablakban)
    phone = common.fix_phone(row.get('phone', '')).strip()
    if phone:
        digits = re.sub(r'[^\d+]', '', phone)
        if len(re.sub(r'\D', '', digits)) >= 6:
            lines.append(f'{i}  <a class="person-phone" href="tel:{digits}">{esc(phone)}</a>')
        else:
            lines.append(f'{i}  <span class="person-phone">{esc(phone)}</span>')
    lines += [
        f'{i}  <div class="person-bio" hidden>',
        f'{i}    <p class="person-bio-role">{esc(row["role"])}</p>',
    ]
    intro = [line.strip() for line in row.get('intro', '').splitlines() if line.strip()]
    if intro:
        lines.append(f'{i}    <p class="person-bio-text">' + '<br>'.join(esc(line) for line in intro) + '</p>')
    contacts = [f'<a class="person-email" href="mailto:{esc(email)}">{esc(email)}</a>'] if email else []
    if row.get('phone'):
        contacts += common.contact_lines('', row['phone'])
    if contacts:
        lines.append(f'{i}    <ul class="person-bio-contact">')
        lines += [f'{i}      <li>{contact}</li>' for contact in contacts]
        lines.append(f'{i}    </ul>')
    lines += [f'{i}  </div>', f'{i}</div>']
    return '\n'.join(lines)
