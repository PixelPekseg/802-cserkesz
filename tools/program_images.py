"""Programképek és -videók a Google Drive "Képek és videók/Program képek/<mappa>" mappáiból
(a sync_programok.py használja).

A programok táblázatának "Képek" oszlopában a program mappájának NEVE áll (pl. "csm"; a
"Program képek/csm" alak is jó). A mappa minden képe és videója a program kártyájára kerül, név
szerinti sorrendben (összesen legfeljebb MAX_ITEMS darab).

Képek: két WebP készül (letöltve, kicsinyítve):
    images/webp/programok/<mappa-slug>/<név>.webp        nagy (a nagyítóban / a felugró ablakban)
    images/webp/programok/<mappa-slug>/thumb/<név>.webp  bélyegkép (a kártyán)
Videók: NEM töltődnek le – a Drive saját lejátszója játssza le őket az oldalon (kattintásra, a
felugró ablakban). Csak egy előnézeti kép készül a Drive automatikus bélyegképéből (a kártyán
lévő kis változaton lejátszás ikonnal); ha a Drive még nem készítette el, egy zöld, lejátszás
ikonos csempe áll a helyén, és a következő futások újra megpróbálják.

Ha több program ugyanazt a mappát használja, a fájlok csak egyszer tárolódnak. Csak a változott
elemeket dolgozza fel (data/program_kepek.json). A már nem használt mappák fájljai törlődnek.
Nem található mappa → nincs kép a kártyán (figyelmeztetés). Ha nincs API-kulcs, semmit nem
frissít, a meglévők maradnak.
"""
import io
import json
import os
import shutil
import urllib.request

import sync_common as common
from drive_photos import Drive, is_image, is_program_folder, is_video, save_json, slugify, to_webp

DIR_REL = 'images/webp/programok'
DIR = os.path.join(common.ROOT, *DIR_REL.split('/'))
STATE = os.path.join(common.ROOT, 'data', 'program_kepek.json')
FULL_LONG_SIDE = 1400   # a nagyítóban
THUMB_LONG_SIDE = 480   # a kártyán
MAX_ITEMS = 40


def _play_overlay(webp_bytes):
    """Lejátszás ikon (fehér háromszög sötét körben) a kép közepére."""
    from PIL import Image, ImageDraw
    image = Image.open(io.BytesIO(webp_bytes)).convert('RGB')
    draw = ImageDraw.Draw(image, 'RGBA')
    w, h = image.size
    r = max(18, min(w, h) // 7)
    cx, cy = w // 2, h // 2
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(20, 35, 24, 170))
    t = r * 0.45
    draw.polygon([(cx - t * 0.8, cy - t), (cx - t * 0.8, cy + t), (cx + t, cy)], fill=(255, 255, 255, 235))
    out = io.BytesIO()
    image.save(out, 'WEBP', quality=75, method=6)
    return out.getvalue()


def _placeholder(width):
    """Zöld 3:2-es csempe (ha a Drive még nem készített előnézetet a videóhoz)."""
    from PIL import Image
    image = Image.new('RGB', (width, width * 2 // 3), (56, 102, 65))
    out = io.BytesIO()
    image.save(out, 'WEBP', quality=80)
    return out.getvalue()


def folder_parts(folder_name):
    """A táblázatba írt mappanév → (útvonal részei a Program… mappán belül, a tárolási mappa neve)."""
    parts = [p.strip() for p in folder_name.strip().strip('/').split('/') if p.strip()]
    if len(parts) > 1 and is_program_folder({'mimeType': 'application/vnd.google-apps.folder', 'name': parts[0]}):
        parts = parts[1:]
    return parts, '-'.join(slugify(p) for p in parts)


def on_disk(state, slug):
    """A tárolt mappa elemei az állapot alapján: [{'thumb', 'full', 'video'}, ...]."""
    entry = state.get(slug, {})
    files = entry.get('files', {})
    result = []
    for name in entry.get('order', []):
        full = f'{DIR_REL}/{slug}/{name}.webp'
        thumb = f'{DIR_REL}/{slug}/thumb/{name}.webp'
        if os.path.exists(os.path.join(common.ROOT, full)) and os.path.exists(os.path.join(common.ROOT, thumb)):
            info = files.get(name, {})
            result.append({'thumb': thumb, 'full': full,
                           'video': info.get('id') if info.get('kind') == 'video' else None})
    return result


class ProgramImages:
    def __init__(self):
        self.drive = Drive()
        try:
            with open(STATE, encoding='utf-8') as handle:
                self.state = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            self.state = {}
        self.used = set()
        self.synced = set()
        self.updated = []
        self.warned_disabled = False

    def images_for(self, folder_name, where):
        """A mappa elemei: [{'thumb', 'full', 'video'}, ...] (a 'video' a Drive-azonosító vagy None)."""
        parts, slug = folder_parts(folder_name)
        if not slug:
            return []
        self.used.add(slug)
        if slug not in self.synced:
            self.synced.add(slug)
            if self.drive.enabled:
                self._sync(parts, slug, where)
            elif not self.warned_disabled:
                common.warn('Nincs GOOGLE_API_KEY / DRIVE_KEPEK_FOLDER_ID, a programképeket most nem frissítem.')
                self.warned_disabled = True
        return self._on_disk(slug)

    def _on_disk(self, slug):
        return on_disk(self.state, slug)

    def _find_folder(self, parts):
        program_root = next((i for i in self.drive.children(self.drive.root_id) if is_program_folder(i)), None)
        if not program_root:
            return None
        folder = program_root
        for part in parts:
            folder = self.drive.subfolder(folder['id'], part)
            if not folder:
                return None
        return folder

    def _poster(self, item):
        """A videó Drive-os előnézeti képe (bájtok), vagy None, ha még nincs."""
        link = item.get('thumbnailLink')
        if not link:
            return None
        link = link.replace('=s220', '=s1600')   # nagyobb változat
        try:
            with urllib.request.urlopen(link, timeout=30) as response:
                return response.read()
        except Exception:
            return None

    def _sync(self, parts, slug, where):
        from PIL import UnidentifiedImageError
        target = os.path.join(DIR, slug)
        folder = self._find_folder(parts)
        if not folder:
            common.warn(f'{where}: a(z) "{"/".join(parts)}" mappa nem található a Program képek mappában, '
                        'a kártyán nem lesz kép.')
            self._drop(slug)
            return
        items = sorted((i for i in self.drive.children(folder['id']) if is_image(i) or is_video(i)),
                       key=lambda i: i['name'].lower())
        if len(items) > MAX_ITEMS:
            common.warn(f'{where}: a mappában {len(items)} kép/videó van, csak az első {MAX_ITEMS}-et teszem ki.')
            items = items[:MAX_ITEMS]
        if not items:
            common.warn(f'{where}: a(z) "{"/".join(parts)}" mappában nincs kép vagy videó.')

        old = self.state.get(slug, {}).get('files', {})
        files, order = {}, []
        for item in items:
            video = is_video(item)
            base = slugify(os.path.splitext(item['name'])[0])
            name, n = base, 2
            while name in files:
                name, n = f'{base}-{n}', n + 1
            full_path = os.path.join(target, f'{name}.webp')
            thumb_path = os.path.join(target, 'thumb', f'{name}.webp')
            stamp = Drive.stamp(item)
            if video:
                stamp.update({'kind': 'video', 'id': item['id']})
            previous = old.get(name, {})
            unchanged = {k: v for k, v in previous.items() if k != 'poster'} == stamp
            # videónál újrapróbáljuk, ha legutóbb még nem volt Drive-előnézet
            retry_poster = video and not previous.get('poster') and item.get('thumbnailLink')
            if unchanged and not retry_poster and os.path.exists(full_path) and os.path.exists(thumb_path):
                files[name] = previous
                order.append(name)
                continue
            try:
                if video:
                    poster = self._poster(item)
                    if poster:
                        full = to_webp(poster, max_long=FULL_LONG_SIDE, quality=78)
                        thumb = _play_overlay(to_webp(poster, max_long=THUMB_LONG_SIDE, quality=72))
                    else:
                        full = _placeholder(960)
                        thumb = _play_overlay(_placeholder(THUMB_LONG_SIDE))
                    stamp['poster'] = bool(poster)
                else:
                    data = self.drive.download(item)
                    full = to_webp(data, max_long=FULL_LONG_SIDE, quality=78)
                    thumb = to_webp(data, max_long=THUMB_LONG_SIDE, quality=72)
            except UnidentifiedImageError:
                common.warn(f'{where}: a(z) "{item["name"]}" nem olvasható képként, kihagyva.')
                continue
            except Exception as error:
                common.warn(f'{where}: a(z) "{item["name"]}" most nem tölthető le ({error}).')
                if previous and os.path.exists(full_path) and os.path.exists(thumb_path):
                    files[name] = previous     # a régi változat marad
                    order.append(name)
                continue
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            for path, content in ((full_path, full), (thumb_path, thumb)):
                with open(path, 'wb') as handle:
                    handle.write(content)
            files[name] = stamp
            order.append(name)
            self.updated.append(f'{slug}/{name}' + (' (videó)' if video else ''))

        # a mappából törölt elemek
        for sub in (target, os.path.join(target, 'thumb')):
            if os.path.isdir(sub):
                for entry in os.listdir(sub):
                    if entry.endswith('.webp') and entry[:-5] not in files:
                        os.remove(os.path.join(sub, entry))
        self.state[slug] = {'folder': '/'.join(parts), 'files': files, 'order': order}

    def _drop(self, slug):
        target = os.path.join(DIR, slug)
        if os.path.isdir(target):
            shutil.rmtree(target)
            self.updated.append(f'{slug} (törölve)')
        self.state.pop(slug, None)

    def finish(self):
        """A már egyik program által sem használt mappák fájljainak törlése, állapot mentése."""
        if self.drive.enabled:
            for slug in list(self.state):
                if slug not in self.used:
                    self._drop(slug)
            if os.path.isdir(DIR):
                for entry in os.listdir(DIR):
                    if entry not in self.used and os.path.isdir(os.path.join(DIR, entry)):
                        shutil.rmtree(os.path.join(DIR, entry))
        save_json(STATE, self.state)
