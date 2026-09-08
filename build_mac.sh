#!/usr/bin/env bash
# Run inside a virtual environment installed from requirements-dev.txt.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${AIDITOR_PYTHON:-python3}"
APP_NAME="AI-ditor Plus"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/aiditor-build.XXXXXX")"
trap 'rm -rf "$TEMP_ROOT"' EXIT
"$PYTHON" -c "import flask, docx, PIL, webview, PyInstaller"
"$PYTHON" -m unittest discover -s tests -q
"$PYTHON" -m PyInstaller aiditor_plus.spec --noconfirm --workpath "$TEMP_ROOT/work" --distpath dist
codesign --force --deep --sign - "dist/$APP_NAME.app"
codesign --verify --deep --strict "dist/$APP_NAME.app"
mkdir -p "$TEMP_ROOT/dmg"
ditto "dist/$APP_NAME.app" "$TEMP_ROOT/dmg/$APP_NAME.app"
ln -s /Applications "$TEMP_ROOT/dmg/Applications"
hdiutil create -volname "$APP_NAME 2.0.0" -srcfolder "$TEMP_ROOT/dmg" -ov -format UDZO "dist/AIditorPlus_Installer.dmg"
hdiutil verify "dist/AIditorPlus_Installer.dmg"
"$PYTHON" -c "from pathlib import Path; import hashlib; p=Path('dist/AIditorPlus_Installer.dmg'); Path('dist/SHA256SUMS.txt').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')"
echo "Ready: dist/AIditorPlus_Installer.dmg"
