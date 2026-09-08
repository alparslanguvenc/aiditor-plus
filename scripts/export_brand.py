"""Export the shared SVG mark to macOS, Windows and PNG application assets.

Requires requirements-dev.txt and `python -m playwright install chromium`.
Run from any directory: python scripts/export_brand.py
"""
from pathlib import Path
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    svg = (ROOT / 'static/brand.svg').read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='aiditor-brand-') as temporary:
        png = Path(temporary) / 'master.png'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={'width': 1024, 'height': 1024}, device_scale_factor=1)
            page.set_content('<style>html,body{margin:0;background:transparent}svg{display:block;width:1024px;height:1024px}</style>' + svg)
            page.screenshot(path=str(png), omit_background=True)
            browser.close()
        with Image.open(png) as master:
            master.save(ROOT / 'aiditor_plus_icon.png', optimize=True)
            master.save(ROOT / 'icon_plus.icns', format='ICNS')
            master.save(ROOT / 'icon_plus.ico', format='ICO',
                        sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    print('Exported PNG (1024), ICNS (16–1024), and ICO (16–256).')


if __name__ == '__main__':
    main()
