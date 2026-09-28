"""Shared running-page preferences and safe article placeholders for Word/LaTeX."""
import math
import re

TOKENS = {
    'dergi': 'Dergi adı', 'dergi_en': 'İngilizce dergi adı', 'baslik': 'Makale başlığı',
    'kisa_baslik': 'Kısa başlık', 'yazarlar': 'Kısa yazar bilgisi', 'yil': 'Yıl',
    'cilt': 'Cilt', 'sayi': 'Sayı', 'sayfa': 'Sayfa numarası', 'doi': 'DOI', 'issn': 'ISSN',
}
TOKEN_RE = re.compile(r'\{([a-z_]+)\}')
RUNNING_DEFAULTS = {}
for _kind in ('header', 'footer'):
    RUNNING_DEFAULTS.update({f'{_kind}_mode': 'standard', f'{_kind}_first_mode': 'none',
                             f'{_kind}_font_size': '8', f'{_kind}_rule': 'none'})
    for _variant in ('', '_even', '_first'):
        for _slot in ('left', 'center', 'right'):
            RUNNING_DEFAULTS[f'{_kind}{_variant}_{_slot}'] = ''
RUNNING_DEFAULTS.update(header_left='{dergi}', header_right='{kisa_baslik}',
                        header_even_left='{kisa_baslik}', header_even_right='{dergi}',
                        footer_center='{sayfa}', footer_even_center='{sayfa}', footer_first_center='{sayfa}')


def normalize_running(raw: dict) -> dict:
    result = {**RUNNING_DEFAULTS, **{key: raw[key] for key in RUNNING_DEFAULTS if key in raw}}
    for key, value in result.items():
        if key.endswith('_first_mode'):
            choices = {'none', 'inherit', 'custom'}
        elif key.endswith('_mode'):
            choices = {'standard', 'same', 'odd_even', 'none'}
        elif key.endswith('_font_size'):
            choices = {'7', '8', '9', '10'}
        elif key.endswith('_rule'):
            choices = {'none', 'line'}
        else:
            if not isinstance(value, str) or len(value) > 180 or value.count('\n') > 2 or any(ord(c) < 32 and c != '\n' for c in value):
                raise ValueError('Üst/alt bilgi alanları en fazla 180 karakter ve 3 satır olmalıdır.')
            for token in TOKEN_RE.findall(value):
                if token not in TOKENS:
                    raise ValueError('Bilinmeyen üst/alt bilgi alanı: {' + token + '}')
            continue
        if str(value) not in choices:
            raise ValueError(f'Geçersiz üst/alt bilgi seçimi: {key}')
        result[key] = str(value)
    return result


def article_values(data: dict, settings: dict) -> dict:
    cov = data.get('cover', {})
    english = settings.get('english_only', False)
    title = ((cov.get('en_title') or cov.get('tr_title')) if english else (cov.get('tr_title') or cov.get('en_title'))) or ''
    names = [a.get('name', '').split()[-1] for a in data.get('authors', []) if a.get('name', '').strip()]
    authors = cov.get('author_short') or (' & '.join(names) if len(names) <= 2 else names[0] + ' et al.')
    journal = (settings.get('journal_name_en') or settings.get('journal_name_tr')) if english else (settings.get('journal_name_tr') or settings.get('journal_name_en'))
    return {'dergi': journal or '', 'dergi_en': settings.get('journal_name_en', ''), 'baslik': title,
            'kisa_baslik': title if len(title) <= 100 else title[:97].rstrip() + '…', 'yazarlar': authors,
            'yil': cov.get('year', ''), 'cilt': cov.get('volume', ''), 'sayi': cov.get('issue', ''),
            'doi': cov.get('doi', ''), 'issn': settings.get('issn_online') or settings.get('issn_print', '')}


def citation_text(data: dict, settings: dict) -> str:
    values = article_values(data, settings)
    cov = data.get('cover', {})
    parts = [values['yazarlar'], '(' + values['yil'] + ').' if values['yil'] else '', values['baslik'] + '.' if values['baslik'] else '',
             settings.get('journal_name_en') or values['dergi']]
    issue = values['cilt'] + ('(' + values['sayi'] + ')' if values['sayi'] else '')
    if issue:
        parts.append(issue + ',')
    pages = '–'.join(str(cov.get(key, '')) for key in ('start_page', 'end_page') if cov.get(key))
    if pages:
        parts.append(pages + '.')
    return ' '.join(part for part in parts if part)


def running_slots(settings: dict, data: dict, kind: str, variant: str) -> tuple[str, str, str]:
    if variant == 'first':
        first = settings[f'{kind}_first_mode']
        if first == 'none':
            return ('', '', '')
        if first == 'custom':
            return tuple(settings[f'{kind}_first_{slot}'] for slot in ('left', 'center', 'right'))
        start = str(data.get('cover', {}).get('start_page', '1'))
        variant = 'even' if start.isdigit() and int(start) % 2 == 0 else 'odd'
    mode = settings[f'{kind}_mode']
    if mode == 'none':
        return ('', '', '')
    if mode == 'standard':
        return ('', citation_text(data, settings) if kind == 'header' else '{sayfa}', '')
    suffix = '_even' if mode == 'odd_even' and variant == 'even' else ''
    return tuple(settings[f'{kind}{suffix}_{slot}'] for slot in ('left', 'center', 'right'))


def resolved_parts(text: str, values: dict):
    """Yield ('text', value) or ('page', '') without interpreting user content as code."""
    position = 0
    for match in TOKEN_RE.finditer(text):
        yield 'text', text[position:match.start()]
        token = match.group(1)
        yield ('page', '') if token == 'sayfa' else ('text', values.get(token, match.group(0)))
        position = match.end()
    yield 'text', text[position:]


def block_height_cm(settings: dict, data: dict, kind: str) -> float:
    """Reserve generous running-text space without fixing/clipping header row height."""
    size = int(settings[f'{kind}_font_size'])
    values = article_values(data, settings)
    lines = 1
    for variant in ('first', 'odd', 'even'):
        slots = running_slots(settings, data, kind, variant)
        only_center = not slots[0] and not slots[2]
        chars = (155 if only_center else 46) * 8 / size
        for slot in slots:
            expanded = ''.join('99999' if kind_ == 'page' else part for kind_, part in resolved_parts(slot, values))
            count = sum(max(1, math.ceil(len(line) / chars)) for line in expanded.split('\n'))
            lines = max(lines, count)
    return max(.65, lines * size * 1.3 * 2.54 / 72 + .25)
