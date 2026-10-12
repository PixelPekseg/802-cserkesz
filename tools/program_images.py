"""Programképek a Google Drive "Képek/Program képek/<mappa>" mappáiból (a sync_programok.py használja).

A programok táblázatának "Képek" oszlopában a program képeit tartalmazó mappa NEVE áll (pl. "csm";
a "Program képek/csm" alak is jó). A mappa minden képe a program kártyájára kerül, név szerinti
sorrendben (legfeljebb MAX_IMAGES darab). Minden képből két WebP készül:
    images/webp/programok/<mappa-slug>/<kép-slug>.webp        nagy (a nagyítóban látszik)
    images/webp/programok/<mappa-slug>/thumb/<kép-slug>.webp  bélyegkép (a kártyán)
Ha több program ugyanazt a mappát használja, a képek csak egyszer tárolódnak.
Csak a változott képeket tölti le (data/program_kepek.json). A már nem használt mappák képei
törlődnek. Nem található mappa → nincs kép a kártyán (figyelmeztetés). Ha nincs API-kulcs, semmit
nem frissít, a meglévő képek maradnak.
"""
import json
import os
import shutil

import sync_common as common
from drive_photos import PROGRAM_FOLDER, Drive, is_image, save_json, slugify, to_webp

DIR_REL = 'images/webp/programok'
DIR = os.path.join(common.ROOT, *DIR_REL.split('/'))
STATE = os.path.join(common.ROOT, 'data', 'program_kepek.json')
FULL_LONG_SIDE = 1400   # a nagyítóban
THUMB_LONG_SIDE = 480   # a kártyán ~80 px magas sáv, 2-3x-os kijelzőre is elég
MAX_IMAGES = 40


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
        """A mappa képei: [(bélyegkép, nagy kép), ...] relatív útvonalakkal."""
        folder_name = folder_name.strip().strip('/')
        if not folder_name:
            return []
        parts = [p.strip() for p in folder_name.split('/') if p.strip()]
        if parts and parts[0].lower() == PROGRAM_FOLDER:
            parts = parts[1:]
        if not parts:
            return []
        slug = '-'.join(slugify(p) for p in parts)
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
        names = self.state.get(slug, {}).get('order', [])
        result = []
        for name in names:
            full = f'{DIR_REL}/{slug}/{name}.webp'
            thumb = f'{DIR_REL}/{slug}/thumb/{name}.webp'
            if os.path.exists(os.path.join(common.ROOT, full)) and os.path.exists(os.path.join(common.ROOT, thumb)):
                result.append((thumb, full))
        return result

    def _find_folder(self, parts):
        program_root = self.drive.subfolder(self.drive.root_id, PROGRAM_FOLDER)
        if not program_root:
            return None
        folder = program_root
        for part in parts:
            folder = self.drive.subfolder(folder['id'], part)
            if not folder:
                return None
        return folder

    def _sync(self, parts, slug, where):
        from PIL import UnidentifiedImageError
        target = os.path.join(DIR, slug)
        folder = self._find_folder(parts)
        if not folder:
            common.warn(f'{where}: a(z) "{"/".join(parts)}" mappa nem található a Képek/Program képek mappában, '
                        'a kártyán nem lesz kép.')
            self._drop(slug)
            return
        items = sorted((i for i in self.drive.children(folder['id']) if is_image(i)), key=lambda i: i['name'].lower())
        if len(items) > MAX_IMAGES:
            common.warn(f'{where}: a mappában {len(items)} kép van, csak az első {MAX_IMAGES}-et teszem ki.')
            items = items[:MAX_IMAGES]
        if not items:
            common.warn(f'{where}: a(z) "{"/".join(parts)}" mappában nincs kép.')

        old = self.state.get(slug, {}).get('files', {})
        files, order = {}, []
        for item in items:
            base = slugify(os.path.splitext(item['name'])[0])
            name, n = base, 2
            while name in files:
                name, n = f'{base}-{n}', n + 1
            full_path = os.path.join(target, f'{name}.webp')
            thumb_path = os.path.join(target, 'thumb', f'{name}.webp')
            stamp = Drive.stamp(item)
            if old.get(name) == stamp and os.path.exists(full_path) and os.path.exists(thumb_path):
                files[name] = stamp
                order.append(name)
                continue
            try:
                data = self.drive.download(item)
                full = to_webp(data, max_long=FULL_LONG_SIDE, quality=78)
                thumb = to_webp(data, max_long=THUMB_LONG_SIDE, quality=72)
            except UnidentifiedImageError:
                common.warn(f'{where}: a(z) "{item["name"]}" nem olvasható képként, kihagyva.')
                continue
            except Exception as error:
                common.warn(f'{where}: a(z) "{item["name"]}" most nem tölthető le ({error}).')
                if name in old and os.path.exists(full_path) and os.path.exists(thumb_path):
                    files[name] = old[name]     # a régi változat marad
                    order.append(name)
                continue
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            for path, content in ((full_path, full), (thumb_path, thumb)):
                with open(path, 'wb') as handle:
                    handle.write(content)
            files[name] = stamp
            order.append(name)
            self.updated.append(f'{slug}/{name}')

        # a mappából törölt képek
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
        """A már egyik program által sem használt mappák képeinek törlése, állapot mentése."""
        if self.drive.enabled:
            for slug in list(self.state):
                if slug not in self.used:
                    self._drop(slug)
            if os.path.isdir(DIR):
                for entry in os.listdir(DIR):
                    if entry not in self.used and os.path.isdir(os.path.join(DIR, entry)):
                        shutil.rmtree(os.path.join(DIR, entry))
        save_json(STATE, self.state)
