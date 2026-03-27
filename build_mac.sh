#!/usr/bin/env bash
# ============================================================
# build_mac.sh — AI-ditor Plus macOS DMG builder
# Run from the Journal_Formatter directory:
#   chmod +x build_mac.sh && ./build_mac.sh
# ============================================================
set -e

APP_NAME="AI-ditor Plus"
SPEC_FILE="aiditor_plus.spec"
ICON_SRC="aiditor_plus_icon.png"
ICNS_FILE="icon_plus.icns"
DMG_NAME="AIditorPlus_Installer.dmg"
VOLUME_NAME="AI-ditor Plus"

echo "=== AI-ditor Plus macOS Builder ==="

# ── 1. Install / upgrade PyInstaller ──────────────────────
pip install --upgrade pyinstaller pillow

# ── 2. Rebuild .icns if source PNG exists ─────────────────
if [ -f "$ICON_SRC" ]; then
  echo "Building icon..."
  ICONSET_DIR="icon_plus.iconset"
  mkdir -p "$ICONSET_DIR"
  for SIZE in 16 32 64 128 256 512; do
    sips -z $SIZE $SIZE "$ICON_SRC" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png" > /dev/null 2>&1
    DOUBLE=$((SIZE * 2))
    sips -z $DOUBLE $DOUBLE "$ICON_SRC" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}@2x.png" > /dev/null 2>&1
  done
  iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"
  rm -rf "$ICONSET_DIR"
  echo "Icon built: $ICNS_FILE"
fi

# ── 3. Clean previous build ───────────────────────────────
rm -rf build/ dist/

# ── 4. Run PyInstaller ────────────────────────────────────
pyinstaller "$SPEC_FILE" --noconfirm

# ── 5. Check output ───────────────────────────────────────
APP_PATH="dist/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
  echo "ERROR: $APP_PATH not found. Build failed."
  exit 1
fi
echo "App bundle created: $APP_PATH"

# ── 6. Create DMG ─────────────────────────────────────────
echo "Creating DMG..."
rm -f "dist/${DMG_NAME}"
hdiutil create \
  -volname "$VOLUME_NAME" \
  -srcfolder "$APP_PATH" \
  -ov -format UDZO \
  "dist/${DMG_NAME}"

echo ""
echo "=== BUILD COMPLETE ==="
echo "DMG: dist/${DMG_NAME}"
echo ""
echo "To distribute: send only 'dist/${DMG_NAME}' to authorized users."
