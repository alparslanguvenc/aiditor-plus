"""AI-ditor Plus: a local, account-isolated academic journal workspace."""
import argparse
import base64
import binascii
import copy
import io
import json
import os
import re
import sqlite3
import sys
import threading
from urllib.parse import urlsplit
import uuid
import webbrowser
import zipfile

from flask import Flask, jsonify, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from account_store import AccountStore, DuplicateUsername, RevisionConflict, check_id, data_directory
from journal_templates import TEMPLATES, default_settings, normalize_settings
from formatter import generate_latex_from_form, extract_form_data_from_docx, _normalize_table_model

APP_VERSION = '2.0.2'


def resource_path(relative_path):
    return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), relative_path)


app = Flask(__name__, template_folder=resource_path('templates'), static_folder=resource_path('static'))
app.config.update(MAX_CONTENT_LENGTH=32 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_NAME='aiditor_plus_session',
                  SESSION_REFRESH_EACH_REQUEST=False)
app.secret_key = AccountStore().session_secret()
_zip_store = {}
_docx_import_store = {}
_cache_lock = threading.RLock()


def account_store():
    return AccountStore(app.config.get('AIDITOR_DATA_DIR') or data_directory())


def current_user():
    return account_store().user(session.get('account_id')) if session.get('account_id') else None


def cache_put(store, key, owner, value):
    def size(item):
        value = item['value']
        return len(value) if isinstance(value, bytes) else sum(len(image['bytes']) for image in value)
    with _cache_lock:
        store[key] = {'owner': owner, 'value': value}
        while len(store) > 12 or (len(store) > 1 and sum(size(item) for item in store.values()) > 128 * 1024 * 1024):
            store.pop(next(iter(store)), None)


def cache_get(store, key):
    with _cache_lock:
        item = store.get(key)
        return item['value'] if item and item['owner'] == session.get('account_id') else None


def json_object():
    if not request.is_json:
        raise ValueError('İstek JSON biçiminde olmalıdır.')
    value = request.get_json()
    if not isinstance(value, dict):
        raise ValueError('İstek bir JSON nesnesi olmalıdır.')
    return value


def parse_json(raw, default=None):
    try:
        return json.loads(raw) if raw is not None else default
    except (ValueError, TypeError) as exc:
        raise ValueError('JSON verisi okunamadı.') from exc


def read_docx(upload):
    if not upload or not upload.filename or not upload.filename.lower().endswith('.docx'):
        raise ValueError('Lütfen .docx biçiminde bir Word dosyası seçin.')
    blob = upload.read()
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            entries = archive.infolist()
            if len(entries) > 5000 or sum(i.file_size for i in entries) > 128 * 1024 * 1024:
                raise ValueError('Word dosyasının açılmış boyutu çok büyük (en fazla 128 MB).')
            if 'word/document.xml' not in archive.namelist():
                raise ValueError('Dosya geçerli bir Word belgesi değil.')
    except zipfile.BadZipFile as exc:
        raise ValueError('Word dosyası okunamadı; boş, bozuk veya parola korumalı olabilir.') from exc
    return blob


def validate_form(data, draft=False):
    if not isinstance(data, dict):
        raise ValueError('Form verisi bir JSON nesnesi olmalıdır.')
    for key in ('cover', 'abstract', 'extra'):
        if not isinstance(data.get(key, {}), dict):
            raise ValueError(f'{key}: alan yapısı geçersiz.')
        if any(not isinstance(value, str) for value in data.get(key, {}).values()):
            raise ValueError(f'{key}: alanlar metin olmalıdır.')
    for key in ('authors', 'sections', 'figtables'):
        if not isinstance(data.get(key, []), list) or any(not isinstance(v, dict) for v in data.get(key, [])):
            raise ValueError(f'{key}: liste yapısı geçersiz.')
    if not isinstance(data.get('references', ''), str):
        raise ValueError('Kaynakça metin olmalıdır.')
    for author in data.get('authors', []):
        for field in ('name', 'affiliation', 'email', 'orcid', 'title'):
            if not isinstance(author.get(field, ''), str):
                raise ValueError('Yazar bilgileri metin olmalıdır.')
        orcid = re.sub(r'^https?://orcid\.org/', '', author.get('orcid', ''), flags=re.I).strip()
        if not draft and orcid and not re.fullmatch(r'\d{4}-\d{4}-\d{4}-\d{3}[\dXx]', orcid):
            raise ValueError('ORCID, 0000-0000-0000-0000 biçiminde olmalıdır.')
        if not draft:
            author['orcid'] = orcid.upper()
        if 'corresponding' in author and not isinstance(author['corresponding'], bool):
            raise ValueError('Sorumlu yazar seçimi doğru/yanlış değeri olmalıdır.')
    section_ids = set()
    for section in data.get('sections', []):
        if any(not isinstance(section.get(k, ''), str) for k in ('name', 'content')):
            raise ValueError('Bölüm başlığı ve içeriği metin olmalıdır.')
        if str(section.get('level', '1')) not in {'1', '2', '3'}:
            raise ValueError('Bölüm düzeyi 1, 2 veya 3 olmalıdır.')
        section['level'] = str(section.get('level', '1'))
        sid = section.get('id')
        if sid is not None:
            if not isinstance(sid, (str, int)) or isinstance(sid, bool) or str(sid) in section_ids:
                raise ValueError('Bölüm kimlikleri geçerli ve birbirinden farklı olmalıdır.')
            section_ids.add(str(sid))
    for ft in data.get('figtables', []):
        if ft.get('type') not in {'figure', 'table'}:
            raise ValueError('Şekil/tablo türü geçersiz.')
        if not draft and not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', str(ft.get('number', '1'))):
            raise ValueError('Şekil/tablo numarası geçersiz.')
        if ft.get('section_id') is not None and not isinstance(ft['section_id'], (str, int)):
            raise ValueError('Şekil/tablo bölüm kimliği geçersiz.')
        for field in ('tr_cap', 'en_cap', 'section', 'after_para', 'tbl_data', 'file_key'):
            if not isinstance(ft.get(field, ''), str):
                raise ValueError('Şekil/tablo alanları metin olmalıdır.')
        model = ft.get('tbl_model')
        if model is not None:
            if not isinstance(model, dict) or not isinstance(model.get('rows'), list):
                raise ValueError('Tablo hücre yapısı geçersiz.')
            if len(model['rows']) > 500 or any(not isinstance(row, list) or len(row) > 100 for row in model['rows']):
                raise ValueError('Bir tablo en fazla 500 satır ve 100 hücre/satır içerebilir.')
            for row in model['rows']:
                for index, cell in enumerate(row):
                    if isinstance(cell, str):
                        cell = row[index] = {'text': cell}
                    if not isinstance(cell, dict) or not isinstance(cell.get('text', ''), str):
                        raise ValueError('Tablo hücreleri metin içermelidir.')
                    for field, limit in (('colspan', 50), ('rowspan', 100)):
                        value = cell.get(field, 1)
                        if not re.fullmatch(r'[0-9]{1,3}', str(value)) or not 1 <= int(value) <= limit:
                            raise ValueError(f'Tablo {field} değeri 1–{limit} arasında tam sayı olmalıdır.')
                    for field in ('align', 'bgcolor', 'textcolor'):
                        if not isinstance(cell.get(field, ''), str):
                            raise ValueError('Tablo hücre biçimi geçersiz.')
                    for field in ('bold', 'italic', 'underline'):
                        if field in cell and not isinstance(cell[field], bool):
                            raise ValueError('Tablo hücre biçimi doğru/yanlış değeri olmalıdır.')
            # Normalize once, including the true column count with merged cells,
            # before either rendering the editor or generating the document.
            normalized = _normalize_table_model(ft)
            ft['tbl_model'] = {key: normalized[key] for key in ('rows', 'header_rows', 'grid_borders')}
            ft['tbl_model']['column_widths'] = normalized['widths']
    cov = data.get('cover', {})
    doi = re.sub(r'^DOI\s*:\s*', '', cov.get('doi', '').strip(), flags=re.I)
    doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi, flags=re.I)
    if not draft and doi and not re.fullmatch(r'10\.\d{4,9}/[^\s{}\\]+', doi):
        raise ValueError('DOI geçersiz. Örnek: 10.1234/dergi.2026.001')
    if not draft and 'doi' in cov:
        cov['doi'] = doi
    for field in ('start_page', 'end_page'):
        value = cov.get(field, '')
        if not draft and value and value != 'xxx' and (not value.isdigit() or not 1 <= int(value) <= 99999):
            raise ValueError('Sayfa numarası pozitif bir tam sayı olmalıdır.')
    start, end = cov.get('start_page', ''), cov.get('end_page', '')
    if not draft and start.isdigit() and end.isdigit() and int(end) < int(start):
        raise ValueError('Bitiş sayfası başlangıç sayfasından küçük olamaz.')



def validate_image(name, blob, *, allow_pdf=True, max_bytes=8 * 1024 * 1024):
    if not isinstance(name, str) or not name or len(name) > 200 or '/' in name or '\\' in name or name.startswith('.'):
        raise ValueError('Görsel dosya adı geçersiz.')
    ext = name.rsplit('.', 1)[-1].lower()
    allowed = {'png', 'jpg', 'jpeg', 'pdf'} if allow_pdf else {'png', 'jpg', 'jpeg'}
    if ext not in allowed:
        raise ValueError('Görseller PNG veya JPG olmalıdır.' if not allow_pdf else 'Şekiller PNG, JPG veya PDF olmalıdır.')
    if not blob or len(blob) > max_bytes:
        raise ValueError(f'Görsel dosyası boş veya {max_bytes // (1024 * 1024)} MB sınırını aşıyor.')
    if ext == 'pdf':
        if not blob.startswith(b'%PDF-') or b'%%EOF' not in blob[-4096:]:
            raise ValueError('PDF dosyası geçersiz.')
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(blob), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 200:
                raise ValueError
            # XeLaTeX includes the first page. Validate the page tree and bounds
            # without expanding embedded image/content streams into memory.
            for page in reader.pages:
                if not 0 < float(page.mediabox.width) <= 14400 or not 0 < float(page.mediabox.height) <= 14400:
                    raise ValueError
        except Exception as exc:
            raise ValueError('PDF okunamadı; şifresiz, geçerli ve en fazla 200 sayfalık bir dosya seçin.') from exc
    else:
        from docx.image.image import Image
        try:
            image = Image.from_blob(blob)
            from PIL import Image as RasterImage
            with RasterImage.open(io.BytesIO(blob)) as raster:
                raster.verify()
            with RasterImage.open(io.BytesIO(blob)) as raster:
                if raster.width * raster.height > 40_000_000:
                    raise ValueError
                raster.load()
            expected = 'image/png' if ext == 'png' else 'image/jpeg'
            if image.content_type != expected or image.px_width <= 0 or image.px_height <= 0 or image.px_width * image.px_height > 40_000_000:
                raise ValueError
        except Exception as exc:
            raise ValueError('Görsel içeriği veya dosya uzantısı geçersiz; okunabilir bir PNG/JPG seçin.') from exc
    return ext


def decode_asset(value, *, allow_pdf=True, max_bytes=8 * 1024 * 1024):
    if not isinstance(value, dict):
        raise ValueError('Görsel verisi geçersiz.')
    name, encoded = value.get('name'), value.get('data')
    if not isinstance(encoded, str) or len(encoded) > (max_bytes * 4 // 3 + 1024):
        raise ValueError('Görsel verisi boyut sınırını aşıyor.')
    match = re.fullmatch(r'data:([\w/+.-]+);base64,([A-Za-z0-9+/=]+)', encoded)
    if not match:
        raise ValueError('Görsel base64 veri biçiminde olmalıdır.')
    try:
        blob = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError('Görsel verisi çözülemedi.') from exc
    ext = validate_image(name, blob, allow_pdf=allow_pdf, max_bytes=max_bytes)
    expected = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'pdf': 'application/pdf'}[ext]
    if match.group(1) != expected:
        raise ValueError('Görsel içerik türü dosya uzantısıyla eşleşmiyor.')
    return name, blob, ext


def validate_assets(assets):
    if not isinstance(assets, dict) or any(key not in {'logo', 'license'} for key in assets):
        raise ValueError('Dergi görselleri geçersiz.')
    result = {}
    for key, asset in assets.items():
        if asset is None:
            result[key] = None
        else:
            name, blob, ext = decode_asset(asset)
            mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'pdf': 'application/pdf'}[ext]
            result[key] = {'name': name, 'data': f'data:{mime};base64,' + base64.b64encode(blob).decode('ascii')}
    return result


def read_figure_files():
    figures = {}
    for field, upload in request.files.items():
        if not field.startswith('fig_') or not upload or not upload.filename:
            continue
        key = field[4:]
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', key):
            raise ValueError('Şekil dosya anahtarı geçersiz.')
        blob = upload.read()
        ext = validate_image(upload.filename, blob, allow_pdf=True, max_bytes=16 * 1024 * 1024)
        figures[key] = (f'fig_{key}.{ext}', blob)
    return figures


def validate_draft_project(project):
    if not isinstance(project, dict) or project.get('format') not in {'aiditor-project', 'jgttr-project'} or type(project.get('version')) is not int or project['version'] != 1:
        raise ValueError('Bu dosya desteklenen bir makale projesi değil.')
    data = project.get('data')
    if not isinstance(data, dict) or any(key not in data for key in ('cover', 'abstract', 'authors', 'sections', 'figtables')):
        raise ValueError('Proje alanları eksik.')
    validate_form(copy.deepcopy(data), draft=True)
    if 'journal_settings' in project:
        normalize_settings(project['journal_settings'])
    if 'journal_assets' in project:
        validate_assets(project['journal_assets'])
    figures = project.get('figures', {})
    if not isinstance(figures, dict) or len(figures) > 200:
        raise ValueError('Projedeki şekil listesi geçersiz.')
    total = 0
    for key, asset in figures.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', key):
            raise ValueError('Projedeki şekil anahtarı geçersiz.')
        _, blob, _ = decode_asset(asset, allow_pdf=True, max_bytes=16 * 1024 * 1024)
        total += len(blob)
    if total > 32 * 1024 * 1024:
        raise ValueError('Projedeki şekillerin toplamı 32 MB sınırını aşıyor.')
    for item in data['figtables']:
        if item['type'] == 'figure' and item.get('file_key') not in figures and item.get('file_missing') is not True:
            raise ValueError('Projedeki şekil dosyası eksik.')


@app.before_request
def local_requests_only():
    try:
        if urlsplit(request.host_url).hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError
    except ValueError:
        return jsonify(ok=False, error='AI-ditor Plus yalnızca yerel uygulama adresinden kullanılabilir.'), 403
    if request.path.startswith('/api/articles'):
        request.max_content_length = 48 * 1024 * 1024
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        origin = request.headers.get('Origin')
        try:
            if origin and (urlsplit(origin).netloc != request.host or urlsplit(origin).scheme != request.scheme):
                raise ValueError
        except ValueError:
            return jsonify(ok=False, error='İşlemi AI-ditor Plus uygulama sayfasından başlatın.'), 403
        if request.headers.get('X-Aiditor-Request') != '1':
            return jsonify(ok=False, error='İstek uygulama sayfasından gönderilmelidir.'), 403
    public = request.path in {'/', '/health', '/license', '/api/templates', '/api/auth/session', '/api/auth/register', '/api/auth/login'} or request.path.startswith('/static/')
    if public:
        return None
    user = current_user()
    if not user:
        return jsonify(ok=False, error='Devam etmek için dergi hesabına giriş yapın.', code='login_required'), 401
    # Resource tags/download links cannot send custom headers; their cache owner
    # still has to match the authenticated account before any bytes are returned.
    resource = request.path.startswith('/download/') or re.fullmatch(r'/import_docx/[^/]+/image/\d+', request.path)
    if not resource and request.headers.get('X-Aiditor-Account') != user['id']:
        return jsonify(ok=False, error='Bu penceredeki dergi hesabı değişti. Sayfayı yenileyerek doğru hesapla devam edin.', code='account_changed'), 409


@app.after_request
def private_responses(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


@app.errorhandler(HTTPException)
def http_error(error):
    limit = 48 if request.path.startswith('/api/articles') else 32
    message = f'Yüklenen dosyaların toplamı {limit} MB sınırını aşıyor.' if error.code == 413 else error.description
    return jsonify(ok=False, error=message), error.code


@app.errorhandler(ValueError)
def invalid_input(error):
    return jsonify(ok=False, error=str(error)), 400


@app.errorhandler(RevisionConflict)
def revision_conflict(error):
    return jsonify(ok=False, error='Bu kayıt başka bir pencerede güncellendi. Değişikliklerinizi yedekleyip güncel kaydı açın.', code='revision_conflict'), 409


@app.errorhandler(sqlite3.Error)
@app.errorhandler(OSError)
def storage_error(error):
    app.logger.exception('Local storage is unavailable')
    return jsonify(ok=False, error='Yerel kayıt alanına ulaşılamadı. Disk alanını ve klasör izinlerini kontrol edin.'), 503


@app.route('/')
def index():
    return render_template('index.html', app_version=APP_VERSION)


@app.route('/license')
def license_text():
    return send_file(resource_path('LICENSE'), mimetype='text/plain; charset=utf-8', as_attachment=False)


@app.route('/health')
def health():
    return jsonify(ok=True, app='AI-ditor Plus', version=APP_VERSION, storage='local')


@app.route('/api/auth/session')
def auth_session():
    return jsonify(ok=True, user=current_user())


def account_credentials(payload, registration=False):
    username, password = payload.get('username'), payload.get('password')
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}', username.strip()):
        raise ValueError('Kullanıcı adı 3–40 karakter olmalı; harf, rakam, nokta, alt çizgi veya tire içermelidir.')
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        raise ValueError('Parola 8–256 karakter olmalıdır.')
    display = payload.get('display_name', username.strip())
    if registration and (not isinstance(display, str) or not 2 <= len(display.strip()) <= 120 or any(ord(c) < 32 for c in display)):
        raise ValueError('Dergi adı 2–120 karakter olmalıdır.')
    return username.strip().lower(), password, display.strip() if isinstance(display, str) else ''


@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    username, password, display_name = account_credentials(json_object(), registration=True)
    settings = default_settings()
    settings['journal_name_tr'] = display_name
    try:
        user = account_store().register(username, display_name, password, settings)
    except DuplicateUsername as exc:
        return jsonify(ok=False, error=str(exc)), 409
    session.clear()
    session['account_id'] = user['id']
    return jsonify(ok=True, user=user), 201


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    username, password, _ = account_credentials(json_object())
    user = account_store().authenticate(username, password)
    if not user:
        return jsonify(ok=False, error='Kullanıcı adı veya parola hatalı.'), 401
    session.clear()
    session['account_id'] = user['id']
    return jsonify(ok=True, user=user)


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify(ok=True, user=None)


@app.route('/api/templates')
def journal_templates():
    return jsonify(ok=True, templates=TEMPLATES)


@app.route('/validate_journal', methods=['POST'])
def validate_journal():
    payload = json_object()
    if 'settings' not in payload:
        raise ValueError('Dergi ayarları eksik.')
    settings = normalize_settings(payload['settings'])
    assets = validate_assets(payload.get('assets', {}))
    return jsonify(ok=True, settings=settings, assets=assets)


@app.route('/api/journal', methods=['GET', 'PUT'])
def journal_settings():
    store, owner = account_store(), session['account_id']
    if request.method == 'GET':
        result = store.journal(owner)
        result['settings'] = normalize_settings(result['settings'])
        return jsonify(ok=True, **result)
    payload = json_object()
    if 'settings' not in payload:
        raise ValueError('Dergi ayarları eksik.')
    settings = normalize_settings(payload['settings'])
    assets = validate_assets(payload.get('assets', {}))
    return jsonify(ok=True, **store.save_journal(owner, settings, assets, payload.get('base_revision')))


@app.route('/api/articles')
def list_articles():
    return jsonify(ok=True, articles=account_store().articles(session['account_id']))


@app.route('/api/articles/<article_id>', methods=['GET', 'PUT', 'DELETE'])
def saved_article(article_id):
    store, owner = account_store(), session['account_id']
    if request.method == 'GET':
        article = store.article(owner, article_id)
        if article is None:
            return jsonify(ok=False, error='Kayıtlı makale bulunamadı.'), 404
        return jsonify(ok=True, article=article)
    payload = json_object()
    if request.method == 'DELETE':
        if not store.delete_article(owner, article_id, payload.get('base_revision')):
            return jsonify(ok=False, error='Kayıtlı makale bulunamadı.'), 404
        return jsonify(ok=True)
    project = payload.get('project')
    validate_draft_project(project)
    return jsonify(ok=True, article=store.save_article(owner, article_id, project, payload.get('base_revision')))


@app.route('/validate_form', methods=['POST'])
def validate_project_data():
    data = parse_json(request.form.get('data'), {})
    validate_form(data, draft=request.form.get('draft') == '1')
    if request.form.get('check_figures') == '1':
        figures = read_figure_files()
        for item in data.get('figtables', []):
            if item['type'] == 'figure' and item.get('file_key') not in figures and item.get('file_missing') is not True:
                raise ValueError(f"Şekil {item.get('number', '')} proje dosyasında eksik.")
    return jsonify(ok=True, data=data)


def generation_assets(saved):
    assets = {}
    for key, field, stem in (('logo', 'logo_upload', 'journal_logo'), ('license', 'ccby_upload', 'journal_license')):
        upload = request.files.get(field)
        if upload and upload.filename:
            blob = upload.read()
            ext = validate_image(upload.filename, blob)
        elif saved.get(key):
            _, blob, ext = decode_asset(saved[key])
        else:
            continue
        assets[key] = (f'{stem}.{ext}', blob)
    return assets


@app.route('/process_form', methods=['POST'])
def process_form():
    data = parse_json(request.form.get('data'))
    validate_form(data)
    figures = read_figure_files()
    for item in data.get('figtables', []):
        if item['type'] == 'figure' and item.get('file_key') not in figures:
            raise ValueError(f"Şekil {item.get('number', '')} için görsel dosyası eksik.")
    saved = account_store().journal(session['account_id'])
    settings = normalize_settings(parse_json(request.form.get('journal_settings'), saved['settings']))
    assets = generation_assets(saved['assets'])
    # Controlled names prevent uploaded figures from colliding with journal assets.
    settings['logo_stem'], settings['cc_logo_stem'] = 'journal_logo', 'journal_license'
    try:
        tex = generate_latex_from_form(data, figures, settings)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('main.tex', tex.encode('utf-8'))
            for filename, blob in list(assets.values()) + list(figures.values()):
                archive.writestr(filename, blob)
            archive.writestr('journal_settings.json', json.dumps(settings, ensure_ascii=False, indent=2).encode('utf-8'))
            archive.writestr('README_Overleaf.txt', (
                'AI-ditor Plus — Overleaf Kullanımı\n\n'
                '1. Overleaf → New Project → Upload Project ile bu ZIP dosyasını yükleyin.\n'
                '2. Compiler ayarından XeLaTeX seçin.\n'
                '3. Recompile ile PDF oluşturun ve sayfa düzenini kontrol edin.\n\n'
                'AI-ditor Plus, akademik dergi editörlerinin işlerini kolaylaştırmak amacıyla\n'
                'kâr amacı güdülmeden geliştirilen, MIT lisanslı özgür bir uygulamadır.\n'
                'Uygulamanın MIT lisansı makalenizin veya derginizin yayın lisansını değiştirmez.\n'
            ).encode('utf-8'))
        key = str(uuid.uuid4())
        cache_put(_zip_store, key, session['account_id'], buf.getvalue())
        return jsonify(ok=True, key=key)
    except (ValueError, HTTPException):
        raise
    except Exception:
        app.logger.exception('Article generation failed')
        return jsonify(ok=False, error='Çıktı oluşturulamadı; form ve tablo alanlarını kontrol edin.'), 500


@app.route('/download/<key>')
def download(key):
    blob = cache_get(_zip_store, key)
    if blob is None:
        return jsonify(ok=False, error='Dosya bulunamadı; çıktıyı bu dergi hesabında yeniden oluşturun.'), 404
    return send_file(io.BytesIO(blob), mimetype='application/zip', as_attachment=True, download_name='aiditor_article.zip')


@app.route('/import_docx', methods=['POST'])
def import_docx():
    blob = read_docx(request.files.get('article'))
    try:
        data, images = extract_form_data_from_docx(blob)
        key = str(uuid.uuid4())
        cache_put(_docx_import_store, key, session['account_id'], images)
        return jsonify(ok=True, import_key=key, data=data)
    except (ValueError, HTTPException):
        raise
    except Exception:
        return jsonify(ok=False, error='Word dosyası okunamadı; bozuk veya parola korumalı olabilir.'), 400


@app.route('/import_docx/<import_key>/image/<int:image_index>')
def imported_docx_image(import_key, image_index):
    images = cache_get(_docx_import_store, import_key)
    if images is None or not 0 <= image_index < len(images):
        return jsonify(ok=False, error='Görsel bulunamadı.'), 404
    image = images[image_index]
    return send_file(io.BytesIO(image['bytes']), mimetype=image.get('mimetype', 'application/octet-stream'),
                     as_attachment=False, download_name=secure_filename(image.get('filename', 'image.png')) or 'image.png')


def create_local_server(port=5051):
    from werkzeug.serving import make_server
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('Bağlantı noktası 0–65535 arasında olmalıdır.')
    for candidate in range(port, min(port + (1 if port == 0 else 5), 65536)):
        try:
            return make_server('127.0.0.1', candidate, app, threaded=True)
        except (OSError, SystemExit):
            continue
    raise RuntimeError('Yerel bağlantı noktaları dolu. --port 0 ile boş bir bağlantı noktası seçin.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Yerel AI-ditor Plus dergi çalışma alanı')
    parser.add_argument('--port', type=int)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--browser', action='store_true', help='Masaüstü penceresi yerine tarayıcıda aç')
    args = parser.parse_args()
    desktop_mode = not args.no_browser and not args.browser
    if desktop_mode:
        try:
            import webview
        except ImportError:
            desktop_mode = False
    server = create_local_server(args.port if args.port is not None else (0 if desktop_mode else 5051))
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'AI-ditor Plus {APP_VERSION}: {url}', flush=True)
    if desktop_mode:
        from desktop import run_desktop
        run_desktop(server)
    else:
        if not args.no_browser:
            threading.Timer(0.5, webbrowser.open, args=[url]).start()
        try:
            server.serve_forever()
        finally:
            server.server_close()
