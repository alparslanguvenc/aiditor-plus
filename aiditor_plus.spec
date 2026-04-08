# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 6.x uyumlu — macOS .app bundle
import os
BASE = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(BASE, 'app.py')],
    pathex=[BASE],
    binaries=[],
    datas=[
        (os.path.join(BASE, 'templates'), 'templates'),
        (os.path.join(BASE, 'aiditor_plus_icon.png'), '.'),
        (os.path.join(BASE, 'JGTTR.png'), '.'),
        (os.path.join(BASE, 'ccby.png'), '.'),
        (os.path.join(BASE, 'formatter.py'), '.'),
    ],
    hiddenimports=[
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
    a.binaries,
    a.datas,
    [],
    name='AI-ditor Plus',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=True,
    icon=os.path.join(BASE, 'icon_plus.icns'),
)

app = BUNDLE(
    exe,
    name='AI-ditor Plus.app',
    icon=os.path.join(BASE, 'icon_plus.icns'),
    bundle_identifier='com.aiditorplus.app',
    info_plist={
        'CFBundleName':               'AI-ditor Plus',
        'CFBundleDisplayName':        'AI-ditor Plus',
        'CFBundleVersion':            '1.1.0',
        'CFBundleShortVersionString': '1.1',
        'NSHighResolutionCapable':    True,
        'LSMinimumSystemVersion':     '11.0',
    },
)
