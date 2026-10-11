"""Személyfotók a Google Drive "Képek" mappájából – közös rész a sync_vezetok.py és a
sync_eszkozok.py számára.

A táblázatban csak a Drive-on lévő fájl NEVÉT adják meg (kiterjesztéssel). A modul a Drive
API-val kilistázza a nyilvános mappát (GOOGLE_API_KEY + DRIVE_KEPEK_FOLDER_ID), név szerint
megkeresi a fájlt (kis/nagybetű nem számít; azonos névnél a legutóbb módosított), letölti,
EXIF szerint elforgatja, kicsinyíti, és WebP-be menti az images/webp/kozos/team/<név-slug>.webp
fájlba. Csak a változott fájlokat tölti le (Drive-azonosító + módosítási idő a
data/fotok.json-ban). Üres fájlnév, nem található vagy nem kép fájl → monogram (a régi fotó
törlődik). Ha nincs API-kulcs, a fotókat nem frissíti (figyelmeztet), a meglévők maradnak –
így a kártyák kulcs nélkül is generálhatók.
Teszteléshez a DRIVE_LOCAL_DIR környezeti változóval egy helyi mappa helyettesítheti a Drive-ot.
"""
import datetime as dt
import io
import json
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
MAX_SHORT_SIDE = 400   # a kártyán legfeljebb ~120 px-es kör, 2x-es kijelzőre is bőven elég
MAX_LONG_SIDE = 600


def slugify(text):
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_text.lower()).strip('-') or 'foto'


def initials(name):
    return ''.join(word[0] for word in name.split()[:2]).upper()


class PhotoSync:
    def __init__(self):
        self.local_dir = os.environ.get('DRIVE_LOCAL_DIR', '')
        self.api_key = os.environ.get('GOOGLE_API_KEY', '')
        self.folder_id = os.environ.get('DRIVE_KEPEK_FOLDER_ID', '')
        self.folder = None          # {kisbetűs név: [fájl, ...]}, első használatkor töltődik
        self.enabled = bool(self.local_dir or (self.api_key and self.folder_id))
        try:
            with open(STATE, encoding='utf-8') as handle:
                self.state = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            self.state = {}
        self.updated = []
        self.warned_disabled = False

    # ---- mappa listázása -------------------------------------------------
    def _list(self):
        if self.folder is not None:
            return self.folder
        files = []
        if self.local_dir:
            for name in os.listdir(self.local_dir):
                full = os.path.join(self.local_dir, name)
                if os.path.isfile(full):
                    modified = dt.datetime.fromtimestamp(os.path.getmtime(full), dt.timezone.utc).isoformat()
                    files.append({'id': full, 'name': name, 'modifiedTime': modified})
        else:
            token = None
            while True:
                params = {
                    'q': f"'{self.folder_id}' in parents and trashed = false",
                    'fields': 'nextPageToken, files(id, name, modifiedTime)',
                    'pageSize': '1000',
                    'key': self.api_key,
                }
                if token:
                    params['pageToken'] = token
                try:
                    with urllib.request.urlopen(f'{API}?{urllib.parse.urlencode(params)}', timeout=30) as response:
                        data = json.load(response)
                except Exception as error:
                    common.fail('A Drive "Képek" mappa listázása nem sikerült (jó a mappa azonosítója, nyilvános a '
                                f'mappa, be van kapcsolva a Drive API, és érvényes az API-kulcs?): {error}')
                files += data.get('files', [])
                token = data.get('nextPageToken')
                if not token:
                    break
        self.folder = {}
        for item in files:
            self.folder.setdefault(item['name'].strip().lower(), []).append(item)
        return self.folder

    def _download(self, item):
        if self.local_dir:
            with open(item['id'], 'rb') as handle:
                return handle.read()
        url = f'{API}/{urllib.parse.quote(item["id"])}?alt=media&key={urllib.parse.quote(self.api_key)}'
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()

    @staticmethod
    def _to_webp(data):
        from PIL import Image, ImageOps
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        scale = min(1, MAX_SHORT_SIDE / min(image.size), MAX_LONG_SIDE / max(image.size))
        if scale < 1:
            image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
        out = io.BytesIO()
        image.save(out, 'WEBP', quality=80, method=6)
        return out.getvalue()

    # ---- egy személy fotója ----------------------------------------------
    def photo_for(self, name, filename, where):
        """A személy fotójának relatív útvonala, vagy None (= monogram).

        Ha elérhető a Drive: üres fájlnév, a mappában nem található vagy nem kép fájl esetén
        monogram (a régi fotófájl törlődik). Ha a letöltés átmenetileg nem sikerül, vagy nincs
        API-kulcs, a meglévő fotó marad."""
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
        matches = self._list().get(filename.strip().lower())
        if not matches:
            common.warn(f'{where}: a(z) "{filename}" nem található a Képek mappában (pontosan egyezik a név, '
                        'a kiterjesztéssel együtt?). Monogram jelenik meg.')
            return False
        if len(matches) > 1:
            common.warn(f'{where}: több "{filename}" nevű fájl is van; a legutóbb módosítottat használom.')
        item = max(matches, key=lambda m: m.get('modifiedTime', ''))
        stamp = {'file': item['name'], 'id': item['id'] if not self.local_dir else item['name'],
                 'modified': item.get('modifiedTime', '')}
        if self.state.get(target_name) == stamp and os.path.exists(target_path):
            return True
        try:
            webp = self._to_webp(self._download(item))
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
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        text = json.dumps(self.state, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        old = open(STATE, encoding='utf-8').read() if os.path.exists(STATE) else None
        if old != text:
            with open(STATE, 'w', encoding='utf-8') as handle:
                handle.write(text)
