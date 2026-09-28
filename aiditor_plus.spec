# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 6.x uyumlu — macOS .app bundle
import os
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
BASE = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(BASE, 'app.py')],
    pathex=[BASE],
    binaries=[],
    datas=[
        (os.path.join(BASE, 'templates'), 'templates'),
        (os.path.join(BASE, 'static'), 'static'),
        (os.path.join(BASE, 'LICENSE'), '.'),
        (os.path.join(BASE, 'THIRD_PARTY_NOTICES.md'), '.'),
        (os.path.join(BASE, 'aiditor_plus_icon.png'), '.'),
        (os.path.join(BASE, 'formatter.py'), '.'),
    ] + collect_data_files('webview') + collect_data_files('docx') + collect_data_files('pypdfium2') + collect_data_files('pypdfium2_raw') + copy_metadata('pypdfium2'),
    hiddenimports=[
        'webview', 'webview.platforms.cocoa', 'desktop', 'sqlite3', 'account_store', 'journal_templates',
        'flask', 'flask.templating',
        'werkzeug', 'werkzeug.routing', 'werkzeug.serving',
        'werkzeug.exceptions', 'werkzeug.utils',
        'jinja2', 'jinja2.ext', 'jinja2.loaders',
        'click',
        'docx', 'docx.oxml', 'docx.oxml.ns', 'docx.shared',
        're', 'zipfile', 'json', 'uuid', 'io', 'threading', 'webbrowser',
    ],
    hookspath=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    # python-docx resolves header/footer XML through parts/../templates.
    # Keep the physical package directories as well as the archived modules.
    module_collection_mode={'docx': 'pyz+py'},
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI-ditor Plus',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    icon=os.path.join(BASE, 'icon_plus.icns'),
)

collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AI-ditor Plus')

app = BUNDLE(
    collection,
    name='AI-ditor Plus.app',
    icon=os.path.join(BASE, 'icon_plus.icns'),
    bundle_identifier='com.aiditorplus.app',
    info_plist={
        'CFBundleName':               'AI-ditor Plus',
        'CFBundleDisplayName':        'AI-ditor Plus',
        'CFBundleVersion':            '2.2.0',
        'CFBundleShortVersionString': '2.2.0',
        'NSHighResolutionCapable':    True,
        'LSMinimumSystemVersion':     '13.0',
    },
)
