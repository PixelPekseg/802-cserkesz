"""Person card (photo/monogram, name, role, e-mail, phone; clicking opens a pop-up with the
hidden .person-bio content) – shared by sync_leaders.py, sync_troops.py and sync_equipment.py.
The pop-up is handled by script.js (.person-card.has-bio)."""
import html
import re

import sync_common as common
from drive_photos import initials


def esc(text):
    return html.escape(text, quote=True)


def build_card(row, photo, indent):
    """row: name, role, intro (short introduction, optional), email, phone (optional; when set,
    it appears on the card below the e-mail and in the pop-up as well).
    The pop-up header shows the name and the role (person-bio-role), then the introduction,
    then the contact details."""
    i = indent
    email = row.get('email', '').strip()
    if email and not common.EMAIL.fullmatch(email):
        common.warn(f'{row["name"]}: az e-mail cím nem tűnik érvényesnek, kihagyva: "{email}"')
        email = ''
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
    # the phone number on the card too, below the e-mail (not only in the pop-up)
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
