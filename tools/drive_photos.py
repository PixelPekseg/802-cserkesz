"""Képek a Google Drive "Képek" mappájából – közös rész a sync_vezetok.py, a sync_eszkozok.py és
a sync_programok.py számára.

A nyilvános "Képek és videók" mappát a Drive API-val olvassa (GOOGLE_API_KEY + DRIVE_KEPEK_FOLDER_ID;
az azonosító átnevezéskor sem változik). Szerkezete:
    Képek és videók/
        Csapatvezetés/      személyfotók (és bármely más almappa, illetve maga a gyökér)
        Program képek/      programonként egy-egy almappa (pl. "csm"), benne a képek és videók
                            (bármely "Program…" kezdetű név jó)

Személyfotók (PhotoSync): a táblázatban csak a fájl NEVÉT adják meg (kiterjesztéssel). A modul a
Képek gyökerében és az almappáiban (a "Program képek" kivételével) név szerint keresi (kis/nagybetű
nem számít; azonos névnél a legutóbb módosított), letölti, EXIF szerint elforgatja, kicsinyíti, és
WebP-be menti az images/webp/kozos/team/<név-slug>.webp fájlba. Csak a változott fájlokat tölti le
(data/fotok.json). Üres fájlnév, nem található vagy nem kép fájl → monogram (a régi fotó törlődik).

Ha nincs API-kulcs, semmit nem frissít (figyelmeztet), a meglévő képek maradnak.
Teszteléshez a DRIVE_LOCAL_DIR környezeti változóval egy helyi mappa(fa) helyettesítheti a Drive-ot.
"""
import datetime as dt
import io
import json
import mimetypes
import os
import re
import unicodedata
import urllib.parse
import urllib.request

import sync_common as common

TEAM_DIR_REL = 'images/webp/kozos/team'
TEAM_DIR = os.path.join(common.ROOT, *TEAM_DIR_REL.split('/'))
STATE = os.path.join(common.ROOT, 'data', 'fotok.json')
API = 'https://www.googleapis.com/drive/v3/files'
FOLDER_MIME = 'application/vnd.google-apps.folder'
PROGRAM_FOLDER = 'program'           # a programok almappája: aminek a neve így kezdődik (pl. "Program képek")
MAX_SHORT_SIDE = 400   # személyfotó: a kártyán legfeljebb ~120 px-es kör
MAX_LONG_SIDE = 600


def slugify(text):
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_text.lower()).strip('-') or 'foto'


def initials(name):
    return ''.join(word[0] for word in name.split()[:2]).upper()


def to_webp(data, max_short=None, max_long=None, quality=80):
    """Kép bájtjai → WebP bájtok (EXIF szerinti forgatással, arányos kicsinyítéssel)."""
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGB')
    scale = 1
    if max_short:
        scale = min(scale, max_short / min(image.size))
    if max_long:
        scale = min(scale, max_long / max(image.size))
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, 'WEBP', quality=quality, method=6)
    return out.getvalue()


def is_image(item):
    return item.get('mimeType', '').startswith('image/')


def is_video(item):
    return item.get('mimeType', '').startswith('video/')


def is_program_folder(item):
    return item.get('mimeType') == FOLDER_MIME and item['name'].strip().lower().startswith(PROGRAM_FOLDER)


class Drive:
    """A "Képek" mappa olvasása: a Drive API-val, vagy teszteléshez egy helyi mappából."""

    def __init__(self):
        self.local_dir = os.environ.get('DRIVE_LOCAL_DIR', '')
        self.api_key = os.environ.get('GOOGLE_API_KEY', '')
        self.root_id = self.local_dir or os.environ.get('DRIVE_KEPEK_FOLDER_ID', '')
        self.enabled = bool(self.local_dir or (self.api_key and self.root_id))
        self._cache = {}

    def children(self, folder_id):
        """A mappa közvetlen elemei: [{'id', 'name', 'mimeType', 'modifiedTime'}, ...]"""
        if folder_id in self._cache:
            return self._cache[folder_id]
        items = []
        if self.local_dir:
            for name in sorted(os.listdir(folder_id)):
                full = os.path.join(folder_id, name)
                modified = dt.datetime.fromtimestamp(os.path.getmtime(full), dt.timezone.utc).isoformat()
                mime = FOLDER_MIME if os.path.isdir(full) else (mimetypes.guess_type(name)[0] or '')
                items.append({'id': full, 'name': name, 'mimeType': mime, 'modifiedTime': modified})
        else:
            token = None
            while True:
                params = {
                    'q': f"'{folder_id}' in parents and trashed = false",
                    'fields': 'nextPageToken, files(id, name, mimeType, modifiedTime, thumbnailLink)',
                    'pageSize': '1000',
                    'key': self.api_key,
                }
                if token:
                    params['pageToken'] = token
                try:
                    with urllib.request.urlopen(f'{API}?{urllib.parse.urlencode(params)}', timeout=30) as response:
                        data = json.load(response)
                except Exception as error:
                    common.fail('A Drive "Képek" mappa olvasása nem sikerült (jó a mappa azonosítója, nyilvános a '
                                f'mappa, be van kapcsolva a Drive API, és érvényes az API-kulcs?): {error}')
                items += data.get('files', [])
                token = data.get('nextPageToken')
                if not token:
                    break
        self._cache[folder_id] = items
        return items

    def subfolder(self, folder_id, name):
        """Az adott nevű almappa (kis/nagybetű nem számít), vagy None."""
        for item in self.children(folder_id):
            if item.get('mimeType') == FOLDER_MIME and item['name'].strip().lower() == name.strip().lower():
                return item
        return None

    def download(self, item):
        if self.local_dir:
            with open(item['id'], 'rb') as handle:
                return handle.read()
        url = f'{API}/{urllib.parse.quote(item["id"])}?alt=media&key={urllib.parse.quote(self.api_key)}'
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()

    @staticmethod
    def stamp(item):
        return {'file': item['name'], 'modified': item.get('modifiedTime', '')}


class PhotoSync:
    """Személyfotók (csapatvezetés, eszközös kapcsolattartó)."""

    def __init__(self):
        self.drive = Drive()
        self.enabled = self.drive.enabled
        self.files = None          # {kisbetűs név: [fájl, ...]}, első használatkor töltődik
        try:
            with open(STATE, encoding='utf-8') as handle:
                self.state = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            self.state = {}
        self.updated = []
        self.warned_disabled = False

    def _files(self):
        """A Képek gyökerének és almappáinak (a Program képek kivételével) fájljai név szerint."""
        if self.files is not None:
            return self.files
        self.files = {}
        folders = [self.drive.root_id]
        for item in self.drive.children(self.drive.root_id):
            if item.get('mimeType') == FOLDER_MIME and not is_program_folder(item):
                folders.append(item['id'])
        for folder in folders:
            for item in self.drive.children(folder):
                if item.get('mimeType') != FOLDER_MIME:
                    self.files.setdefault(item['name'].strip().lower(), []).append(item)
        return self.files

    def photo_for(self, name, filename, where):
        """A személy fotójának relatív útvonala, vagy None (= monogram).

        Ha elérhető a Drive: üres fájlnév, nem található vagy nem kép fájl esetén monogram (a régi
        fotófájl törlődik). Ha a letöltés átmenetileg nem sikerül, vagy nincs API-kulcs, a meglévő
        fotó marad."""
        target_name = slugify(name) + '.webp'
        target_path = os.path.join(TEAM_DIR, target_name)
        if not self.enabled:
            if filename and not self.warned_disabled:
                common.warn('Nincs GOOGLE_API_KEY / DRIVE_KEPEK_FOLDER_ID, a fotókat most nem frissítem (a meglévők maradnak).')
                self.warned_disabled = True
        elif not filename or not self._refresh(filename, target_name, target_path, where):
            self._remove(target_name, target_path)
        return f'{TEAM_DIR_REL}/{target_name}' if os.path.exists(target_path) else None

    def _remove(self, target_name, target_path):
        if os.path.exists(target_path):
            os.remove(target_path)
            self.updated.append(f'{target_name} (törölve, monogram)')
        self.state.pop(target_name, None)

    def _refresh(self, filename, target_name, target_path, where):
        """Igaz, ha a fotó megvan (frissítve vagy változatlan, illetve átmeneti letöltési hibánál
        a régi marad); hamis, ha a fájl nem található vagy nem kép (→ monogram)."""
        from PIL import UnidentifiedImageError
        matches = self._files().get(filename.strip().lower())
        if not matches:
            common.warn(f'{where}: a(z) "{filename}" nem található a Képek mappában (pontosan egyezik a név, '
                        'a kiterjesztéssel együtt?). Monogram jelenik meg.')
            return False
        if len(matches) > 1:
            common.warn(f'{where}: több "{filename}" nevű fájl is van; a legutóbb módosítottat használom.')
        item = max(matches, key=lambda m: m.get('modifiedTime', ''))
        stamp = {**Drive.stamp(item), 'id': item['id'] if not self.drive.local_dir else item['name']}
        if self.state.get(target_name) == stamp and os.path.exists(target_path):
            return True
        try:
            webp = to_webp(self.drive.download(item), MAX_SHORT_SIDE, MAX_LONG_SIDE)
        except UnidentifiedImageError:
            common.warn(f'{where}: a(z) "{filename}" nem kép (JPG, PNG, WebP vagy HEIC lehet). Monogram jelenik meg.')
            return False
        except Exception as error:
            common.warn(f'{where}: a(z) "{filename}" most nem tölthető le ({error}); a régi fotó marad, ha van.')
            return True
        os.makedirs(TEAM_DIR, exist_ok=True)
        old = open(target_path, 'rb').read() if os.path.exists(target_path) else None
        if old != webp:
            with open(target_path, 'wb') as handle:
                handle.write(webp)
            self.updated.append(target_name)
        self.state[target_name] = stamp
        return True

    def save_state(self):
        save_json(STATE, self.state)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
    if old != text:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
