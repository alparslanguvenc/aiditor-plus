"""
AI-ditor Plus — Flask Web Application
Generic multi-journal LaTeX formatter.
"""

import os
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_file
import io

from formatter import (extract_from_docx, parse_author_info,
                       generate_latex, build_zip,
                       generate_latex_from_form, build_zip_form)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

PROFILES_DIR = os.path.join(os.path.dirname(__file__), 'profiles')
DEFAULT_LOGO  = os.path.join(os.path.dirname(__file__), 'JGTTR.png')

# In-memory store for generated ZIPs (keyed by session UUID)
_zip_store: dict[str, bytes] = {}


def _safe_name(name: str) -> str:
    """Strip path-traversal characters from profile name."""
    return ''.join(c for c in name if c.isalnum() or c in (' ', '-', '_', '.')).strip()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_form', methods=['POST'])
def process_form():
    """Form-based (structured) LaTeX generation."""
    try:
        raw = request.form.get('data')
        if not raw:
            return jsonify({'ok': False, 'error': 'Form verisi eksik.'}), 400

        data = json.loads(raw)

        # ── Collect figure files ──
        figure_file_bytes = {}
        for field_name, file_obj in request.files.items():
            if field_name.startswith('fig_') and file_obj and file_obj.filename:
                fkey    = field_name[4:]
                ext     = file_obj.filename.rsplit('.', 1)[-1].lower() if '.' in file_obj.filename else 'png'
                zipname = 'fig_' + fkey + '.' + ext
                figure_file_bytes[fkey] = (zipname, file_obj.read())

        # ── Journal settings ──
        js_raw = request.form.get('journal_settings', '{}')
        journal_settings = json.loads(js_raw)

        # Resolve logo — öncelik sırası:
        # 1. Kullanıcının bu formda yüklediği logo (logo_upload)
        # 2. Kaydedilmiş profil logosu (profiles/ klasöründe)
        # 3. Varsayılan JGTTR logosu
        logo_src          = DEFAULT_LOGO
        logo_upload_bytes = None
        logo_upload_fn    = None   # ZIP'e yazılacak tam dosya adı (örn. "dergim.png")

        upload_file = request.files.get('logo_upload')
        if upload_file and upload_file.filename:
            # Orijinal dosya adını kullan (güvenli karakter filtresi ile)
            orig_name      = os.path.basename(upload_file.filename)
            safe_name      = ''.join(c for c in orig_name if c.isalnum() or c in ('_', '-', '.'))
            if not safe_name:
                safe_name  = 'logo.png'
            logo_upload_fn    = safe_name
            logo_upload_bytes = upload_file.read()
            # Logo stem'ini (uzantısız ad) LaTeX üretiminden önce ayarla
            stem = safe_name.rsplit('.', 1)[0] if '.' in safe_name else safe_name
            journal_settings  = dict(journal_settings, logo_stem=stem)
        else:
            logo_filename = journal_settings.get('logo_filename', '')
            if logo_filename:
                candidate = os.path.join(PROFILES_DIR, logo_filename)
                if os.path.exists(candidate):
                    logo_src = candidate

        # LaTeX'i logo stem güncellendikten SONRA üret
        tex = generate_latex_from_form(data, figure_file_bytes, journal_settings)

        if logo_upload_bytes is not None:
            import zipfile as _zf
            buf = io.BytesIO()
            with _zf.ZipFile(buf, 'w', _zf.ZIP_DEFLATED) as zf:
                zf.writestr('main.tex', tex.encode('utf-8'))
                zf.writestr(logo_upload_fn, logo_upload_bytes)
                for fkey, (zipname, filebytes) in figure_file_bytes.items():
                    zf.writestr(zipname, filebytes)
                readme = (
                    "AI-ditor Plus — Overleaf Yükleme Rehberi\n"
                    "=========================================\n\n"
                    "1. Bu ZIP dosyasını açın.\n"
                    "2. Overleaf.com → New Project → Upload Project → ZIP'i seçin.\n"
                    "3. Menu → Compiler → XeLaTeX seçin.\n"
                    "4. Recompile → PDF hazır.\n"
                )
                zf.writestr('README_Overleaf.txt', readme.encode('utf-8'))
            zip_bytes = buf.getvalue()
        else:
            zip_bytes = build_zip_form(tex, logo_src, figure_file_bytes, journal_settings)

        key = str(uuid.uuid4())
        _zip_store[key] = zip_bytes

        return jsonify({'ok': True, 'key': key})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/download/<key>')
def download(key):
    data = _zip_store.get(key)
    if not data:
        return 'Dosya bulunamadı.', 404
    return send_file(
        io.BytesIO(data),
        mimetype='application/zip',
        as_attachment=True,
        download_name='journal_article.zip',
    )


# ── Profile management ──────────────────────────────────────────────────────────

@app.route('/list_profiles')
def list_profiles():
    os.makedirs(PROFILES_DIR, exist_ok=True)
    profiles = sorted(f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith('.json'))
    return jsonify(profiles)


@app.route('/save_profile', methods=['POST'])
def save_profile():
    name = _safe_name(request.form.get('name', ''))
    if not name:
        return jsonify({'ok': False, 'error': 'Profil adı boş olamaz.'}), 400

    settings = json.loads(request.form.get('settings', '{}'))
    os.makedirs(PROFILES_DIR, exist_ok=True)

    # Save logo if provided
    logo_file = request.files.get('logo')
    if logo_file and logo_file.filename:
        ext = logo_file.filename.rsplit('.', 1)[-1].lower() if '.' in logo_file.filename else 'png'
        logo_filename = f'{name}_logo.{ext}'
        logo_file.save(os.path.join(PROFILES_DIR, logo_filename))
        settings['logo_filename'] = logo_filename
        settings['logo_stem']     = f'{name}_logo'

    with open(os.path.join(PROFILES_DIR, f'{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    return jsonify({'ok': True})


@app.route('/load_profile/<name>')
def load_profile(name):
    name = _safe_name(name)
    path = os.path.join(PROFILES_DIR, f'{name}.json')
    if not os.path.exists(path):
        return jsonify({'ok': False, 'error': 'Profil bulunamadı.'}), 404
    with open(path, encoding='utf-8') as f:
        settings = json.load(f)
    return jsonify({'ok': True, 'settings': settings})


@app.route('/delete_profile/<name>', methods=['DELETE'])
def delete_profile(name):
    name = _safe_name(name)
    path = os.path.join(PROFILES_DIR, f'{name}.json')
    if os.path.exists(path):
        os.remove(path)
    for fn in os.listdir(PROFILES_DIR):
        if fn.startswith(name + '_logo.'):
            os.remove(os.path.join(PROFILES_DIR, fn))
    return jsonify({'ok': True})


if __name__ == '__main__':
    import webbrowser, threading
    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open('http://127.0.0.1:5051')
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5051, debug=False)
