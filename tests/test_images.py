"""Portraits (drive_photos), program images and videos (program_images) and the gallery (sync_gallery),
with a local folder instead of Google Drive (DRIVE_LOCAL_DIR) and generated images."""
import io
import json
import os

import pytest
from PIL import Image

import drive_photos
import program_images
import sync_common as common
import sync_gallery
from conftest import block, csv_text
from test_sync_programs import HEADER, program


def image_bytes(size=(1200, 800), color=(200, 50, 50), fmt='JPEG'):
    out = io.BytesIO()
    Image.new('RGB', size, color).save(out, fmt)
    return out.getvalue()


@pytest.fixture
def drive(tmp_path, monkeypatch, paths):
    root = tmp_path / 'Képek és videók'
    (root / 'Csapatvezetés').mkdir(parents=True)
    (root / 'Program képek' / 'okt_23').mkdir(parents=True)
    monkeypatch.setenv('DRIVE_LOCAL_DIR', str(root))
    return root


# ---------- helpers ----------

def test_to_webp_scales_and_converts():
    small = drive_photos.to_webp(image_bytes((1200, 800)), max_short=400, max_long=600)
    image = Image.open(io.BytesIO(small))
    assert image.format == 'WEBP' and image.size == (600, 400)
    palette = io.BytesIO()
    Image.new('P', (10, 10)).save(palette, 'PNG')
    assert Image.open(io.BytesIO(drive_photos.to_webp(palette.getvalue()))).size == (10, 10)   # not enlarged


def test_decompression_bomb_is_refused(monkeypatch):
    from PIL import Image as PILImage
    monkeypatch.setattr(drive_photos, 'MAX_PIXELS', 1000)
    with pytest.raises(PILImage.DecompressionBombError):
        drive_photos.to_webp(image_bytes((100, 100)))       # 10 000 px > 2 × 1000


def test_name_helpers():
    assert drive_photos.slugify('Cseri-Holzman Lili') == 'cseri-holzman-lili'
    assert drive_photos.slugify('???') == 'foto'
    assert drive_photos.initials('Kiss Anna Mária') == 'KA'
    assert drive_photos.is_program_folder({'mimeType': drive_photos.FOLDER_MIME, 'name': ' Program képek '})
    assert not drive_photos.is_program_folder({'mimeType': 'image/jpeg', 'name': 'Program.jpg'})


def test_drive_api_listing_paging_and_errors(monkeypatch, issues):
    monkeypatch.setenv('GOOGLE_API_KEY', 'KEY')
    monkeypatch.setenv('DRIVE_IMAGES_FOLDER_ID', 'ROOT')
    pages = [{'files': [{'id': '1', 'name': 'a.jpg'}], 'nextPageToken': 'N'}, {'files': [{'id': '2', 'name': 'b.jpg'}]}]
    urls = []
    monkeypatch.setattr(common, 'download', lambda url, **k: urls.append(url) or json.dumps(pages.pop(0)).encode())
    drive = drive_photos.Drive()
    assert [f['id'] for f in drive.children('ROOT')] == ['1', '2']
    assert drive.children('ROOT')[0]['id'] == '1' and len(urls) == 2          # cached
    assert 'pageToken=N' in urls[1] and 'key=KEY' in urls[0]

    def broken(url, **k):
        raise common.DownloadError('HTTP 403')
    monkeypatch.setattr(common, 'download', broken)
    with pytest.raises(SystemExit):
        drive_photos.Drive().children('OTHER')
    assert 'képes mappa olvasása nem sikerült' in issues()[0]['message']


def test_drive_api_download_url(monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'K Y')
    monkeypatch.setenv('DRIVE_IMAGES_FOLDER_ID', 'ROOT')
    seen = []
    monkeypatch.setattr(common, 'download', lambda url, **k: seen.append((url, k)) or b'x')
    drive_photos.Drive().download({'id': 'a/b'})
    assert seen[0][0].endswith('/files/a%2Fb?alt=media&key=K%20Y') and seen[0][1] == {'timeout': 60}


# ---------- portraits ----------

def test_photo_found_updated_unchanged_and_removed(drive, paths):
    (drive / 'Csapatvezetés' / 'Lili.JPG').write_bytes(image_bytes())
    (drive / 'Program képek' / 'okt_23' / 'lili.jpg').write_bytes(image_bytes(color=(0, 0, 0)))   # not searched
    photos = drive_photos.PhotoSync()
    assert photos.photo_for('Cseri-Holzman Lili', 'lili.jpg', 'x') == 'images/webp/kozos/team/cseri-holzman-lili.webp'
    assert photos.updated == ['cseri-holzman-lili.webp']
    photos.save_state()
    again = drive_photos.PhotoSync()
    assert again.photo_for('Cseri-Holzman Lili', 'LILI.jpg', 'x') and again.updated == []   # unchanged
    assert again.photo_for('Cseri-Holzman Lili', '', 'x') is None                           # empty → monogram
    assert again.updated == ['cseri-holzman-lili.webp (törölve, monogram)']


def test_photo_problems(drive, paths, issues):
    (drive / 'Csapatvezetés' / 'rossz.jpg').write_bytes(b'nem kep')
    (drive / 'Csapatvezetés' / 'dupla.jpg').write_bytes(image_bytes())
    (drive / 'dupla.jpg').write_bytes(image_bytes(color=(0, 255, 0)))
    photos = drive_photos.PhotoSync()
    assert photos.photo_for('A', 'nincs.jpg', 'sor 2') is None
    assert photos.photo_for('B', 'rossz.jpg', 'sor 3') is None
    assert photos.photo_for('C', 'dupla.jpg', 'sor 4')
    messages = ' '.join(i['message'] for i in issues())
    assert 'sor 2: a(z) "nincs.jpg" nem található' in messages and 'sor 3: a(z) "rossz.jpg" nem kép' in messages
    assert 'több "dupla.jpg" nevű fájl' in messages


def test_photo_download_error_keeps_the_old_one(drive, paths, monkeypatch, issues):
    (drive / 'Csapatvezetés' / 'a.jpg').write_bytes(image_bytes())
    photos = drive_photos.PhotoSync()
    path = photos.photo_for('Anna', 'a.jpg', 'x')
    photos.save_state()
    os.utime(drive / 'Csapatvezetés' / 'a.jpg', (1, 1))           # changed on Drive
    broken = drive_photos.PhotoSync()
    monkeypatch.setattr(broken.drive, 'download', lambda item: (_ for _ in ()).throw(TimeoutError('lassú')))
    assert broken.photo_for('Anna', 'a.jpg', 'x') == path
    assert 'most nem tölthető le' in issues()[-1]['message']


def test_photo_without_drive(paths, issues):
    photos = drive_photos.PhotoSync()
    assert photos.photo_for('Anna', 'a.jpg', 'x') is None
    photos.photo_for('Béla', 'b.jpg', 'x')
    assert len(issues()) == 1                                    # warned once


# ---------- program images ----------

def test_folder_parts():
    assert program_images.folder_parts(' Program képek/ Őszi portya ') == (['Őszi portya'], 'oszi-portya')
    assert program_images.folder_parts('a/b') == (['a', 'b'], 'a-b')
    assert program_images.folder_parts('') == ([], '')


def test_program_images_sync_video_limit_and_cleanup(drive, paths, monkeypatch, issues):
    folder = drive / 'Program képek' / 'okt_23'
    (folder / 'B kép.jpg').write_bytes(image_bytes())
    (folder / 'a kép.png').write_bytes(image_bytes(fmt='PNG'))
    (folder / 'a_kép.jpg').write_bytes(image_bytes())             # the same slug → a-kep-2
    (folder / 'film.mp4').write_bytes(b'video')
    (folder / 'jegyzet.txt').write_text('nem kép')
    (folder / 'hibas.jpg').write_bytes(b'nem kep')
    images = program_images.ProgramImages()
    items = images.images_for('okt_23', 'sor 2')
    names = [os.path.basename(i['full']) for i in items]
    assert names == ['a-kep.webp', 'a-kep-2.webp', 'b-kep.webp', 'film.webp']
    assert items[-1]['video'] == str(folder / 'film.mp4')            # the local "id"
    assert 'hibas.jpg" nem olvasható képként' in issues()[0]['message']
    assert images.images_for('okt_23', 'sor 3') == items              # the same folder: synced once
    images.finish()
    (folder / 'B kép.jpg').unlink()
    again = program_images.ProgramImages()
    assert len(again.images_for('Program képek/okt_23', 'x')) == 3
    assert not (paths / 'images' / 'webp' / 'programok' / 'okt-23' / 'b-kep.webp').exists()
    monkeypatch.setattr(program_images, 'MAX_ITEMS', 2)
    limited = program_images.ProgramImages()
    limited.state = {}
    assert len(limited.images_for('okt_23', 'x')) == 2 and 'csak az első 2-et' in issues()[-1]['message']


def test_program_images_missing_and_empty_folder_and_cleanup(drive, paths, issues):
    (drive / 'Program képek' / 'ures').mkdir()
    stored = paths / 'images' / 'webp' / 'programok' / 'regi'
    stored.mkdir(parents=True)
    (stored / 'x.webp').write_bytes(b'x')
    images = program_images.ProgramImages()
    images.state = {'regi': {'files': {}, 'order': []}}
    assert images.images_for('nincs ilyen', 'sor 2') == []
    assert images.images_for('ures', 'sor 3') == []
    images.finish()
    assert not stored.exists() and 'regi' not in images.state
    messages = ' '.join(i['message'] for i in issues())
    assert '"nincs ilyen" mappa nem található' in messages and '"ures" mappában nincs kép' in messages


def test_program_images_names_differing_only_in_accents(drive, paths, issues):
    (drive / 'Program képek' / 'Őszi').mkdir()
    (drive / 'Program képek' / 'Oszi').mkdir()
    images = program_images.ProgramImages()
    images.images_for('Őszi', 'a')
    assert images.images_for('Oszi', 'b') == []
    assert 'csak ékezetben vagy írásjelben tér el' in issues()[-1]['message']


def test_program_images_keep_files_without_image_column(drive, paths):
    stored = paths / 'images' / 'webp' / 'programok' / 'regi'
    stored.mkdir(parents=True)
    images = program_images.ProgramImages()
    images.finish(allow_delete=False)
    assert stored.exists()


def test_program_images_without_drive(paths, issues):
    images = program_images.ProgramImages()
    assert images.images_for('okt_23', 'x') == [] and images.images_for('mas', 'y') == []
    assert len(issues()) == 1


def test_video_poster_and_retry(paths, monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'K')
    monkeypatch.setenv('DRIVE_IMAGES_FOLDER_ID', 'ROOT')
    tree = {'ROOT': [{'id': 'P', 'name': 'Program képek', 'mimeType': drive_photos.FOLDER_MIME}],
            'P': [{'id': 'F', 'name': 'film', 'mimeType': drive_photos.FOLDER_MIME}],
            'F': [{'id': 'V', 'name': 'v.mp4', 'mimeType': 'video/mp4', 'modifiedTime': '1'}]}
    monkeypatch.setattr(drive_photos.Drive, 'children', lambda self, folder: tree[folder])
    images = program_images.ProgramImages()
    images.images_for('film', 'x')                                       # no thumbnail yet: placeholder
    assert images.state['film']['files']['v']['poster'] is False
    tree['F'][0]['thumbnailLink'] = 'https://lh3.googleusercontent.com/x=s220'
    asked = []
    monkeypatch.setattr(common, 'download', lambda url, **k: asked.append(url) or image_bytes())
    again = program_images.ProgramImages()
    again.state = images.state
    item = again.images_for('film', 'x')[0]
    assert asked == ['https://lh3.googleusercontent.com/x=s1600'] and item['video'] == 'V'
    assert again.state['film']['files']['v']['poster'] is True

    def no_poster(url, **k):
        raise common.DownloadError('404')
    monkeypatch.setattr(common, 'download', no_poster)
    assert program_images.ProgramImages()._poster({'thumbnailLink': 'https://x'}) is None


def test_program_image_download_error_keeps_the_old_version(drive, paths, monkeypatch, issues):
    (drive / 'Program képek' / 'okt_23' / 'a.jpg').write_bytes(image_bytes())
    first = program_images.ProgramImages()
    first.images_for('okt_23', 'x')
    os.utime(drive / 'Program képek' / 'okt_23' / 'a.jpg', (1, 1))
    second = program_images.ProgramImages()
    second.state = first.state
    monkeypatch.setattr(second.drive, 'download', lambda item: (_ for _ in ()).throw(OSError('hálózat')))
    assert len(second.images_for('okt_23', 'x')) == 1
    assert 'most nem tölthető le (hálózat)' in issues()[-1]['message']


def test_inside_dir_safety_net(paths):
    base = program_images.DIR
    assert program_images._inside_dir(os.path.join(base, 'x'))
    assert not program_images._inside_dir(base) and not program_images._inside_dir(os.path.join(base, '..', 'x'))


# ---------- gallery ----------

def test_gallery_sections_alts_and_program_groups(paths, drive, monkeypatch):
    tabor = paths / 'images' / 'webp' / 'tabor'
    (tabor / 'thumb').mkdir(parents=True)
    (tabor / 'a.webp').write_bytes(b'x')
    (tabor / 'thumb' / 'a.webp').write_bytes(b'x')
    (tabor / 'b.webp').write_bytes(b'x')
    (paths / 'tabor.html').write_text('<img src="images/webp/tabor/thumb/a.webp" data-full="images/webp/tabor/a.webp" '
                                      'alt="Tábortűz &amp; ének">', encoding='utf-8')
    (drive / 'Program képek' / 'okt_23' / 'kep.jpg').write_bytes(image_bytes())
    snapshot = paths / 'data' / 'programs.csv'
    snapshot.write_text(csv_text([HEADER, program(Név='Október 23.', Képek='okt_23', **{'Kezdő dátum': '2026.10.23.'}),
                                  program(Név='Másik', Képek='okt_23', **{'Kezdő dátum': '2026.10.01.'}),
                                  program(Név='Kép nélkül', Képek='nincs')]), encoding='utf-8')
    images = program_images.ProgramImages()
    images.images_for('okt_23', 'x')
    images.finish()
    monkeypatch.setattr(sync_gallery.common, 'ROOT', str(paths))
    monkeypatch.setattr('sys.argv', ['sync_gallery.py'])
    sync_gallery.main()
    html = block(paths / 'galeria.html', 'GALLERY')
    assert 'Másik, Október 23. <span class="gallery-date">2026. október 23.</span>' in html   # date of the latest
    assert 'alt="Tábortűz &amp; ének"' in html and 'src="images/webp/tabor/thumb/a.webp"' in html
    assert 'src="images/webp/tabor/b.webp" data-full="images/webp/tabor/b.webp" alt="Tábor – 2. kép"' in html
    assert 'id="galeria-csapatotthonunk"' not in html                     # no images: no section


def test_gallery_without_programs_snapshot(paths, monkeypatch):
    monkeypatch.setattr(sync_gallery.common, 'ROOT', str(paths))
    assert sync_gallery.program_groups() == []


def test_separate_portrait_and_program_folders(paths, monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'K')
    monkeypatch.setenv('DRIVE_LEADERS_FOLDER_ID', 'LEAD')
    monkeypatch.setenv('DRIVE_PROGRAMS_FOLDER_ID', 'PROG')
    jpg = {'mimeType': 'image/jpeg', 'modifiedTime': '1'}
    tree = {'LEAD': [{'id': 'L1', 'name': 'lili.jpg', **jpg},
                     {'id': 'SUB', 'name': 'Program régi', 'mimeType': drive_photos.FOLDER_MIME}],
            'SUB': [{'id': 'L2', 'name': 'anna.jpg', **jpg}],
            'PROG': [{'id': 'F', 'name': 'okt_23', 'mimeType': drive_photos.FOLDER_MIME}],
            'F': [{'id': 'I1', 'name': 'a.jpg', **jpg}]}
    monkeypatch.setattr(drive_photos.Drive, 'children', lambda self, folder: tree[folder])
    monkeypatch.setattr(drive_photos.Drive, 'download', lambda self, item: image_bytes())
    photos = drive_photos.PhotoSync()
    assert photos.photo_for('Lili', 'lili.jpg', 'x') and photos.photo_for('Anna', 'anna.jpg', 'x')   # subfolder too
    assert len(program_images.ProgramImages().images_for('okt_23', 'x')) == 1


def test_only_one_of_the_two_folders(paths, monkeypatch, issues):
    monkeypatch.setenv('GOOGLE_API_KEY', 'K')
    monkeypatch.setenv('DRIVE_PROGRAMS_FOLDER_ID', 'PROG')
    assert not drive_photos.PhotoSync().enabled and program_images.ProgramImages().enabled
    monkeypatch.delenv('DRIVE_PROGRAMS_FOLDER_ID')
    monkeypatch.setenv('DRIVE_LEADERS_FOLDER_ID', 'LEAD')
    images = program_images.ProgramImages()
    assert not images.enabled and images.images_for('okt_23', 'x') == []
    assert 'DRIVE_PROGRAMS_FOLDER_ID' in issues()[-1]['message']
