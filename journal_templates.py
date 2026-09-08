"""Validated, portable journal preferences shared by the UI and formatter.

These presets describe journal typography, not a licence for journal articles.
The application itself is distributed under the MIT licence.
"""
import math
import re
from urllib.parse import urlsplit


TEMPLATES = [
    {'id': 'classic', 'name': 'Klasik akademik',
     'description': 'Solda logo, sağda dergi künyesi; özetlerin yanında makale bilgileri.',
     'settings': {'template_id': 'classic', 'header_layout': 'classic', 'footer_layout': 'full',
                  'font_family': 'texgyrepagella', 'accent_color': '#244E63', 'body_size': '10', 'logo_height_cm': 2.0}},
    {'id': 'contemporary', 'name': 'Çağdaş editoryal',
     'description': 'Renkli dergi başlığı, sağda logo ve yan yana iki dilde özet.',
     'settings': {'template_id': 'contemporary', 'header_layout': 'contemporary', 'footer_layout': 'compact',
                  'font_family': 'texgyreheros', 'accent_color': '#176B68', 'body_size': '10', 'logo_height_cm': 1.7}},
    {'id': 'centered', 'name': 'Ortalanmış kapak',
     'description': 'Ortalanmış logo, dergi adı ve makale başlığı; tam genişlikte özetler.',
     'settings': {'template_id': 'centered', 'header_layout': 'centered', 'footer_layout': 'full',
                  'font_family': 'texgyretermes', 'accent_color': '#603F63', 'body_size': '11', 'logo_height_cm': 1.5}},
    {'id': 'minimal', 'name': 'Yalın araştırma',
     'description': 'Kompakt üst künye, soldan hizalı başlıklar ve sade dipnot alanı.',
     'settings': {'template_id': 'minimal', 'header_layout': 'minimal', 'footer_layout': 'minimal',
                  'font_family': 'latinmodern', 'accent_color': '#333F48', 'body_size': '10', 'logo_height_cm': 1.0}},
]

_DEFAULTS = {
    'journal_name_tr': '', 'journal_name_en': '', 'issn_print': '', 'issn_online': '',
    'journal_url': '', 'font_family': 'texgyrepagella', 'body_size': '10',
    'accent_color': '#244E63', 'logo_height_cm': 2.0, 'corresponding_marker': '*',
    'english_only': False, 'doi_position': 'bottom', 'logo_stem': 'journal_logo',
    'cc_logo_stem': 'license_logo', 'footer_text': '', 'first_page_fit': 'auto',
    'template_id': 'classic', 'header_layout': 'classic', 'footer_layout': 'full',
    'show_logo': True, 'show_cc_logo': True,
}
_FONT_ALIASES = {
    'palatino linotype': 'texgyrepagella', 'palatino': 'texgyrepagella',
    'tex gyre pagella': 'texgyrepagella', 'times new roman': 'texgyretermes',
    'times': 'texgyretermes', 'tex gyre termes': 'texgyretermes',
    'century': 'texgyrebonum', 'century schoolbook': 'texgyrebonum',
    'calibri': 'carlito', 'arial': 'texgyreheros', 'sans serif': 'texgyreheros',
    'sans-serif': 'texgyreheros', 'latin modern': 'latinmodern',
}


def default_settings():
    return dict(_DEFAULTS)


def normalize_settings(raw):
    """Return complete safe settings; reject malformed user supplied values.

    Unknown keys are ignored, so exported preferences can evolve compatibly.
    Legacy `font` and `header_layout` names remain accepted.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError('Dergi ayarları bir nesne olmalıdır.')
    incoming = dict(raw)
    if 'font_family' not in incoming and 'font' in incoming:
        incoming['font_family'] = incoming['font']
    if 'template_id' not in incoming and 'header_layout' in incoming:
        incoming['template_id'] = incoming['header_layout']
    result = default_settings()
    result.update({k: v for k, v in incoming.items() if k in result})
    for key, choices in {
        'template_id': {'classic', 'contemporary', 'centered', 'minimal'},
        'header_layout': {'classic', 'contemporary', 'centered', 'minimal'},
        'footer_layout': {'full', 'compact', 'minimal'},
        'doi_position': {'top', 'bottom'}, 'first_page_fit': {'auto', 'compact', 'dense'},
        'body_size': {'10', '11', '12'},
    }.items():
        value = str(result[key]).strip().lower()
        if value not in choices:
            raise ValueError(f'Geçersiz {key} seçeneği.')
        result[key] = value
    result['header_layout'] = result['template_id']
    font = str(result['font_family']).strip().lower()
    font = _FONT_ALIASES.get(font, font)
    if font not in {'texgyrepagella', 'texgyretermes', 'texgyrebonum', 'texgyreheros', 'carlito', 'latinmodern'}:
        raise ValueError('Desteklenmeyen yazı tipi.')
    result['font_family'] = font
    for key in ('english_only', 'show_logo', 'show_cc_logo'):
        if not isinstance(result[key], bool):
            raise ValueError(f'{key} doğru/yanlış değeri olmalıdır.')
    for key, maximum in {'journal_name_tr': 250, 'journal_name_en': 250, 'issn_print': 30,
                         'issn_online': 30, 'footer_text': 3000, 'journal_url': 500,
                         'corresponding_marker': 4, 'logo_stem': 80, 'cc_logo_stem': 80}.items():
        value = result[key]
        if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError(f'{key} alanı geçerli bir metin olmalıdır (en çok {maximum} karakter).')
        result[key] = value.strip()
    color = result['accent_color']
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Vurgu rengi #RRGGBB biçiminde olmalıdır.')
    result['accent_color'] = color.upper()
    try:
        height = float(result['logo_height_cm'])
    except (TypeError, ValueError):
        raise ValueError('Logo yüksekliği bir sayı olmalıdır.') from None
    if isinstance(result['logo_height_cm'], bool) or not math.isfinite(height) or not 0.5 <= height <= 3.5:
        raise ValueError('Logo yüksekliği 0,5–3,5 cm arasında olmalıdır.')
    result['logo_height_cm'] = height
    url = result['journal_url']
    if url:
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in {'https', 'http'} or not parsed.netloc or parsed.username or parsed.password or any(c.isspace() for c in url):
                raise ValueError
        except ValueError:
            raise ValueError('Dergi adresi geçerli bir http/https adresi olmalıdır.') from None
    for key in ('logo_stem', 'cc_logo_stem'):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', result[key]):
            raise ValueError('Logo dosyası için güvenli bir ad gereklidir.')
    if result['corresponding_marker'] not in {'*', '†', '‡', '§', '¶', '#', '★', '✉'}:
        raise ValueError('Desteklenmeyen sorumlu yazar işareti.')
    return result
