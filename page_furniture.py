"""Shared running-page preferences and safe article placeholders for Word/LaTeX."""
import math
import re

TOKENS = {
    'dergi': 'Dergi adı', 'dergi_en': 'İngilizce dergi adı', 'baslik': 'Makale başlığı',
    'kisa_baslik': 'Kısa başlık', 'yazarlar': 'Kısa yazar bilgisi', 'yil': 'Yıl',
    'cilt': 'Cilt', 'sayi': 'Sayı', 'sayfa': 'Sayfa numarası', 'sayfa_araligi': 'Makalenin sayfa aralığı', 'doi': 'DOI', 'issn': 'ISSN',
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


# Control characters never pass user-field validation, so this marker can only
# come from an automatically calculated last page.
LAST_PAGE = '\x1fson_sayfa\x1f'


def page_value(value) -> str:
    value = str(value or '').strip()
    return '' if value.lower() in {'', 'xxx'} else value


def revision_dates(cov: dict) -> list[str]:
    """Optional revision dates, one per line (semicolons are accepted too)."""
    return [date.strip() for date in re.split(r'[\n;]+', str(cov.get('revisions', '') or '')) if date.strip()]


def short_authors(data: dict) -> str:
    cov = data.get('cover', {})
    names = [a.get('name', '').split()[-1] for a in data.get('authors', []) if a.get('name', '').strip()]
    authors = str(cov.get('author_short', '') or '').strip()
    year = str(cov.get('year', '') or '').strip()
    # Older forms suggested "Yılmaz & Kaya, 2026"; citations add the year themselves.
    if year and re.search(r',?\s*\(?' + re.escape(year) + r'\)?$', authors):
        authors = re.sub(r',?\s*\(?' + re.escape(year) + r'\)?$', '', authors).strip()
    if authors or not names:
        return authors
    return ' & '.join(names) if len(names) <= 2 else names[0] + ' et al.'


def page_range(cov: dict) -> str:
    """Start–end pages; an empty end page is filled from the final layout."""
    start, end = page_value(cov.get('start_page')), page_value(cov.get('end_page'))
    if not start:
        return end
    return start + '–' + (end or LAST_PAGE)


def article_values(data: dict, settings: dict) -> dict:
    cov = data.get('cover', {})
    english = settings.get('english_only', False)
    title = ((cov.get('en_title') or cov.get('tr_title')) if english else (cov.get('tr_title') or cov.get('en_title'))) or ''
    short_title = str(cov.get('short_title', '') or '').strip()
    journal = (settings.get('journal_name_en') or settings.get('journal_name_tr')) if english else (settings.get('journal_name_tr') or settings.get('journal_name_en'))
    return {'dergi': journal or '', 'dergi_en': settings.get('journal_name_en', ''), 'baslik': title,
            'kisa_baslik': short_title or (title if len(title) <= 100 else title[:97].rstrip() + '…'),
            'yazarlar': short_authors(data),
            'yil': cov.get('year', ''), 'cilt': cov.get('volume', ''), 'sayi': cov.get('issue', ''),
            'sayfa_araligi': page_range(cov),
            'doi': cov.get('doi', ''), 'issn': settings.get('issn_online') or settings.get('issn_print', '')}


def citation_text(data: dict, settings: dict) -> str:
    values = article_values(data, settings)
    parts = [values['yazarlar'], '(' + values['yil'] + ').' if values['yil'] else '', values['baslik'] + '.' if values['baslik'] else '',
             settings.get('journal_name_en') or values['dergi']]
    issue = values['cilt'] + ('(' + values['sayi'] + ')' if values['sayi'] else '')
    if issue:
        parts.append(issue + ',')
    if values['sayfa_araligi']:
        parts.append(values['sayfa_araligi'] + '.')
    return ' '.join(part for part in parts if part)


def text_parts(text: str):
    """Split generated text around an automatically calculated last page."""
    for index, part in enumerate(str(text).split(LAST_PAGE)):
        if index:
            yield 'lastpage', ''
        if part:
            yield 'text', part


def running_slots(settings: dict, data: dict, kind: str, variant: str) -> tuple[str, str, str]:
    if variant == 'first':
        first = settings[f'{kind}_first_mode']
        if first == 'none':
            return ('', '', '')
        if first == 'custom':
            slots = tuple(settings[f'{kind}_first_{slot}'] for slot in ('left', 'center', 'right'))
            if (kind == 'header' and settings.get('template_id') == 'bilingual_panel'
                    and slots == ('', 'e-ISSN: {issn} · {cilt}({sayi}) · {yil}', '')
                    and not (settings.get('issn_online') or settings.get('issn_print'))):
                return ('', '{cilt}({sayi}) · {yil}', '')
            return slots
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
    """Yield ('text'|'page'|'lastpage', value) without interpreting user content as code."""
    position = 0
    for match in TOKEN_RE.finditer(text):
        yield from text_parts(text[position:match.start()])
        token = match.group(1)
        if token == 'sayfa':
            yield 'page', ''
        else:
            yield from text_parts(values.get(token, match.group(0)))
        position = match.end()
    yield from text_parts(text[position:])


def block_height_cm(settings: dict, data: dict, kind: str) -> float:
    """Reserve generous running-text space without fixing/clipping header row height."""
    size = int(settings[f'{kind}_font_size'])
    values = article_values(data, settings)
    lines = 1
    for variant in ('first', 'odd', 'even'):
        slots = running_slots(settings, data, kind, variant)
        only_center = not slots[0] and not slots[2]
        chars = (155 if only_center else 46) * 8 / size
        for index, slot in enumerate(slots):
            if settings.get('template_id') == 'scholarly':
                chars = ((125, 1, 12)[index] if not slots[1] and slots[0] else (140 if only_center else 40)) * 8 / size
            expanded = ''.join('99999' if kind_ in {'page', 'lastpage'} else part for kind_, part in resolved_parts(slot, values))
            count = sum(max(1, math.ceil(len(line) / chars)) for line in expanded.split('\n'))
            lines = max(lines, count)
    return max(.65, lines * size * 1.3 * 2.54 / 72 + .25)
