# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 6.x uyumlu — macOS .app bundle
import os
from PyInstaller.utils.hooks import collect_data_files
BASE = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(BASE, 'app.py')],
    pathex=[BASE],
    binaries=[],
    datas=[
        (os.path.join(BASE, 'templates'), 'templates'),
        (os.path.join(BASE, 'static'), 'static'),
        (os.path.join(BASE, 'LICENSE'), '.'),
        (os.path.join(BASE, 'aiditor_plus_icon.png'), '.'),
        (os.path.join(BASE, 'formatter.py'), '.'),
    ] + collect_data_files('webview'),
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
        'CFBundleVersion':            '2.0.1',
        'CFBundleShortVersionString': '2.0.1',
        'NSHighResolutionCapable':    True,
        'LSMinimumSystemVersion':     '11.0',
    },
)
