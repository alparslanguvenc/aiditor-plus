#!/usr/bin/env bash
# Run inside a virtual environment installed from requirements-dev.txt.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${AIDITOR_PYTHON:-python3}"
APP_NAME="AI-ditor Plus"
DMG_NAME="${AIDITOR_DMG_NAME:-AIditorPlus_Installer.dmg}"
VERSION="$("$PYTHON" -c "import pathlib, re; print(re.search(r\"APP_VERSION = '([^']+)'\", pathlib.Path('app.py').read_text()).group(1))")"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/aiditor-build.XXXXXX")"
trap 'rm -rf "$TEMP_ROOT"' EXIT
"$PYTHON" -c "import flask, docx, PIL, webview, PyInstaller"
"$PYTHON" -m unittest discover -s tests -q
"$PYTHON" -m PyInstaller aiditor_plus.spec --noconfirm --workpath "$TEMP_ROOT/work" --distpath dist
codesign --force --deep --sign - "dist/$APP_NAME.app"
codesign --verify --deep --strict "dist/$APP_NAME.app"
ARCHS="$(lipo -archs "dist/$APP_NAME.app/Contents/MacOS/$APP_NAME")"
echo "Built $APP_NAME $VERSION for: $ARCHS"
if [ -n "${AIDITOR_EXPECTED_ARCH:-}" ] && [ "$ARCHS" != "$AIDITOR_EXPECTED_ARCH" ]; then
  echo "Expected $AIDITOR_EXPECTED_ARCH binary, got $ARCHS" >&2
  exit 1
fi
"$PYTHON" scripts/check_package_exports.py "dist/$APP_NAME.app/Contents/MacOS/$APP_NAME"
mkdir -p "$TEMP_ROOT/dmg"
ditto "dist/$APP_NAME.app" "$TEMP_ROOT/dmg/$APP_NAME.app"
ln -s /Applications "$TEMP_ROOT/dmg/Applications"
# Unnotarized apps need one-time approval; ship the steps next to the app.
cp packaging/macos/ILK_ACILIS.txt "$TEMP_ROOT/dmg/İlk Açılış – Okuyun.txt"
hdiutil create -volname "$APP_NAME $VERSION" -srcfolder "$TEMP_ROOT/dmg" -ov -format UDZO "dist/$DMG_NAME"
hdiutil verify "dist/$DMG_NAME"
"$PYTHON" -c "from pathlib import Path; import hashlib, sys; p=Path('dist', sys.argv[1]); Path('dist/SHA256SUMS.txt').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')" "$DMG_NAME"
echo "Ready: dist/$DMG_NAME"
