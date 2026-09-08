"""
AI-ditor Plus Word → LaTeX Formatter
Converts manuscripts to configurable academic journal templates.
Also supports structured form-based input (generate_latex_from_form).
"""

import re
import os
import io
import zipfile
import csv
import math
import unicodedata
from urllib.parse import quote
from journal_templates import normalize_settings
from docx import Document
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph


# ── LaTeX special-character escaping ──────────────────────────────────────────
_LATEX_ESCAPE = str.maketrans({
    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
    '_': r'\_', '{': r'\{', '}': r'\}',
    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    '\\': r'\textbackslash{}',
})

def escape(text: str) -> str:
    if not text:
        return ''
    escaped = text.translate(_LATEX_ESCAPE)
    for digit, subscript in enumerate('₀₁₂₃₄₅₆₇₈₉'):
        escaped = escaped.replace(subscript, rf'\textsubscript{{{digit}}}')
    for digit, superscript in enumerate('⁰¹²³⁴⁵⁶⁷⁸⁹'):
        escaped = escaped.replace(superscript, rf'\textsuperscript{{{digit}}}')
    return escaped


_URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)
_TITLE_FOOTNOTE_MARKER_RE = re.compile(
    r'(?:\s*(?:\*+|[†‡]+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+|'
    r'\\textsuperscript\{(?:\*+|\d+)\}))+\s*$'
)


def _title_without_footnote_marker(title: str) -> str:
    """Keep title footnotes on the cover but omit their marker from page headers."""
    return _TITLE_FOOTNOTE_MARKER_RE.sub('', title or '').rstrip()


def _escape_with_breakable_urls(text: str) -> str:
    """Use one explicit destination for every wrapped fragment of a URL."""
    parts = []
    cursor = 0
    for match in _URL_RE.finditer(text or ''):
        parts.append(escape(text[cursor:match.start()]))
        url = match.group(0)
        trailing = ''
        while url and url[-1] in '.,;':
            trailing = url[-1] + trailing
            url = url[:-1]
        while url.endswith(')') and url.count(')') > url.count('('):
            trailing = ')' + trailing
            url = url[:-1]
        breakable_url = []
        for character in url:
            breakable_url.append(escape(character))
            if character in '/-_.?&=#':
                breakable_url.append(r'\allowbreak{}')
        parts.append(r'\href{' + _url_target(url) + '}{' + ''.join(breakable_url) + '}')
        parts.append(escape(trailing))
        cursor = match.end()
    parts.append(escape((text or '')[cursor:]))
    return ''.join(parts)


def _url_target(url: str) -> str:
    return escape(quote(url, safe=":/?#@!$&'()*+,;=%-._"))


def turkish_sort_key(text: str) -> tuple:
    """Stable Turkish collation, independent of the machine's locale."""
    alphabet = 'abcçdefgğhıijklmnoöpqrsştuüvwxyz'
    ranks = {letter: index for index, letter in enumerate(alphabet)}
    normalized = unicodedata.normalize('NFC', text).translate(str.maketrans({'I': 'ı', 'İ': 'i'})).lower()
    return tuple((0, ranks[c]) if c in ranks else (1, ord(c)) for c in normalized)


def _safe_href_target(text: str) -> str:
    """Keep LaTeX control characters out of href targets."""
    return re.sub(r'[\s{}\\]', '', text or '')


def _clean_orcid(orcid: str) -> str:
    return re.sub(r'[^0-9Xx-]', '', orcid or '')


def _latex_marker(marker: str) -> str:
    marker = (marker or '*').strip()
    marker_map = {
        '*': '*',
        '†': r'\ensuremath{\dagger}',
        '‡': r'\ensuremath{\ddagger}',
        '§': r'\S',
        '¶': r'\P',
        '#': r'\#',
        '★': r'\ensuremath{\star}',
        '✉': r'\Letter',
    }
    return marker_map.get(marker, escape(marker))


def _english_label(text: str) -> str:
    """Return the English half of common bilingual UI labels."""
    value = (text or '').strip()
    if ' -- ' in value:
        value = value.rsplit(' -- ', 1)[-1].strip()
    elif ' / ' in value:
        value = value.rsplit(' / ', 1)[-1].strip()
    return value


def _journal_names_for_output(js: dict, english_only: bool) -> tuple[str, str]:
    """Resolve journal names without showing a Turkish fallback for English-only input."""
    raw_tr = (js.get('journal_name_tr') or '').strip()
    raw_en = (js.get('journal_name_en') or '').strip()

    if not raw_tr and not raw_en:
        raw_tr = 'Akademik Dergi'
        raw_en = 'Academic Journal'

    if english_only and raw_en:
        raw_tr = ''

    return raw_tr, raw_en


# ── Heading / section detection ───────────────────────────────────────────────
SECTION_MAP = {
    # TR keys
    'giriş': 'Giriş / Introduction',
    'introduction': 'Giriş / Introduction',
    'literatür': 'Literatür Taraması / Literature Review',
    'literature': 'Literatür Taraması / Literature Review',
    'literature review': 'Literatür Taraması / Literature Review',
    'kuramsal çerçeve': 'Literatür Taraması / Literature Review',
    'yöntem': 'Yöntem / Methodology',
    'yöntem ve teknik': 'Yöntem / Methodology',
    'methodology': 'Yöntem / Methodology',
    'method': 'Yöntem / Methodology',
    'materials and methods': 'Yöntem / Methodology',
    'bulgular': 'Bulgular / Findings',
    'findings': 'Bulgular / Findings',
    'results': 'Bulgular / Findings',
    'tartışma': 'Tartışma / Discussion',
    'discussion': 'Tartışma / Discussion',
    'sonuç': 'Sonuç / Conclusion',
    'conclusion': 'Sonuç / Conclusion',
    'sonuç ve öneriler': 'Sonuç / Conclusion',
    'conclusions': 'Sonuç / Conclusion',
    'kaynakça': '__REFERENCES__',
    'kaynaklar': '__REFERENCES__',
    'references': '__REFERENCES__',
    'bibliography': '__REFERENCES__',
}

OPTIONAL_END_MATTER_MAP = {
    'teşekkür': 'ack',
    'teşekkürler': 'ack',
    'acknowledgement': 'ack',
    'acknowledgements': 'ack',
    'acknowledgment': 'ack',
    'acknowledgments': 'ack',
    'araştırmacıların katkı oranı': 'contrib',
    'araştırmacı katkı oranı': 'contrib',
    'yazar katkıları': 'contrib',
    'author contribution': 'contrib',
    'author contributions': 'contrib',
    'authors contributions': 'contrib',
    'çıkar çatışması': 'conflict',
    'çıkar çatışması beyanı': 'conflict',
    'conflict of interest': 'conflict',
    'conflicts of interest': 'conflict',
    'declaration of conflict of interest': 'conflict',
}

ABSTRACT_KEYS = {'abstract', 'özet', 'öz'}
KEYWORD_KEYS  = {'keywords', 'anahtar kelimeler', 'anahtar sözcükler', 'key words'}
_SECTION_NUMBER_RE = re.compile(
    r'^\s*(\d+(?:\.\d+){0,2})\s*[.)\-–—]?\s+(.+?)\s*$'
)
_ABSTRACT_LABEL_TOKEN = (
    r'(?:türkçe\s+özet|turkish\s+abstract|ingilizce\s+özet|'
    r'english\s+abstract|ö\s*z\s*e\s*t(?:\s*ç\s*e)?|öz|abstract|summary)'
    r'(?=$|[\s:/&()\-–—\t\n])'
)
_KEYWORD_LABEL_TOKEN = (
    r'(?:anahtar\s+(?:kelimeler|sözcükler)|key\s*words|keywords|'
    r'index\s+terms|indeks\s+terimleri)(?=$|[\s:/&()\-–—\t\n])'
)
_ABSTRACT_LABEL_RE = re.compile(
    rf'^\s*(?P<label>{_ABSTRACT_LABEL_TOKEN})'
    rf'(?:\s*(?:/|&|ve|and|\()\s*{_ABSTRACT_LABEL_TOKEN}\)?)?'
    r'(?:\s*(?::|\-|–|—|\t|\n)\s*|\s+)?(?P<value>.*?)\s*$',
    re.IGNORECASE | re.DOTALL,
)
_KEYWORD_LABEL_RE = re.compile(
    rf'^\s*(?P<label>{_KEYWORD_LABEL_TOKEN})'
    rf'(?:\s*(?:/|&|ve|and|\()\s*{_KEYWORD_LABEL_TOKEN}\)?)?'
    r'(?:\s*(?::|\-|–|—|\t|\n)\s*|\s+)?(?P<value>.*?)\s*$',
    re.IGNORECASE | re.DOTALL,
)


def _para_text(para) -> str:
    return para.text.strip()


def _style_ppr_chain(paragraph: Paragraph):
    style = paragraph.style
    seen = set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        p_pr = getattr(style.element, 'pPr', None)
        if p_pr is not None:
            yield p_pr
        style = style.base_style


def _ppr_level(p_pr, child_name: str) -> int | None:
    if p_pr is None:
        return None
    if child_name == 'outlineLvl':
        element = p_pr.find(qn('w:outlineLvl'))
    else:
        num_pr = p_pr.find(qn('w:numPr'))
        element = num_pr.find(qn('w:ilvl')) if num_pr is not None else None
    if element is None:
        return None
    try:
        raw_level = int(element.get(qn('w:val')))
    except (TypeError, ValueError):
        return None
    # Word uses outline level 9 for body text.
    if raw_level < 0 or (child_name == 'outlineLvl' and raw_level == 9):
        return None
    return min(3, raw_level + 1)


def _paragraph_outline_level(paragraph: Paragraph) -> int | None:
    direct = _ppr_level(paragraph._p.pPr, 'outlineLvl')
    if direct is not None:
        return direct
    for p_pr in _style_ppr_chain(paragraph):
        level = _ppr_level(p_pr, 'outlineLvl')
        if level is not None:
            return level
    return None


def _paragraph_numbering_level(paragraph: Paragraph) -> int | None:
    direct = _ppr_level(paragraph._p.pPr, 'ilvl')
    if direct is not None:
        return direct
    for p_pr in _style_ppr_chain(paragraph):
        level = _ppr_level(p_pr, 'ilvl')
        if level is not None:
            return level
    return None


def _is_heading(para) -> bool:
    style_name = para.style.name if para.style else ''
    return (
        style_name.startswith('Heading')
        or style_name.startswith('Başlık')
        or _paragraph_outline_level(para) is not None
    )


def _heading_level(para) -> int:
    outline_level = _paragraph_outline_level(para)
    if outline_level is not None:
        return outline_level
    name = para.style.name if para.style else ''
    match = re.search(r'\b([1-9])\b', name)
    if match:
        return min(3, int(match.group(1)))
    return 1


def _has_bold(para) -> bool:
    return any(run.bold for run in para.runs if run.text.strip())


def _numbered_section_title(text: str) -> tuple[str, int] | None:
    """Return a heading without its manual number and its inferred level."""
    match = _SECTION_NUMBER_RE.match(text or '')
    if not match:
        return None
    title = match.group(2).strip().rstrip(':').strip()
    if not title:
        return None
    return title, min(3, match.group(1).count('.') + 1)


def _paragraph_is_all_bold(paragraph: Paragraph) -> bool:
    runs = [run for run in paragraph.runs if run.text.strip()]
    return bool(runs) and all(run.bold is True for run in runs)


def _abstract_label_info(text: str) -> tuple[str, str] | None:
    match = _ABSTRACT_LABEL_RE.match(text or '')
    if not match:
        return None
    label = re.sub(r'\s+', ' ', match.group('label').lower()).strip()
    is_english = (
        label.startswith(('english ', 'ingilizce '))
        or label in {'abstract', 'summary'}
    )
    return ('en' if is_english else 'tr'), (match.group('value') or '').strip()


def _keyword_label_info(text: str) -> tuple[str, str] | None:
    match = _KEYWORD_LABEL_RE.match(text or '')
    if not match:
        return None
    label = re.sub(r'\s+', ' ', match.group('label').lower()).strip()
    is_english = 'key' in label or label.startswith('index ')
    return ('en' if is_english else 'tr'), (match.group('value') or '').strip()


def _guess_text_language(text: str) -> str:
    """Choose the abstract field for unlabeled Word abstract paragraphs."""
    lower = f' {text.lower()} '
    tr_score = len(re.findall(
        r'\b(?:bu|çalışma|araştırma|amaç|amacı|yöntem|bulgular|sonuç|ve|ile|için|olarak)\b',
        lower,
    )) + 2 * len(re.findall(r'[çğıöşü]', lower))
    en_score = len(re.findall(
        r'\b(?:this|study|research|aim|purpose|method|findings|results|conclusion|and|with|for)\b',
        lower,
    ))
    return 'tr' if tr_score > en_score else 'en'


def _abstract_style_language(paragraph: Paragraph, text: str) -> str | None:
    style_name = paragraph.style.name.lower() if paragraph.style else ''
    if not any(token in style_name for token in ('abstract', 'özet', 'ozet', 'summary')):
        return None
    if any(token in style_name for token in ('turkish', 'türkçe', 'turkce')):
        return 'tr'
    if any(token in style_name for token in ('english', 'ingilizce')):
        return 'en'
    return _guess_text_language(text)


def _dynamic_section_heading(text: str, paragraph: Paragraph) -> tuple[str, int] | None:
    """Recognize standard and document-specific academic section headings."""
    numbered = _numbered_section_title(text)
    clean_text = numbered[0] if numbered else text.strip().rstrip(':').strip()
    if not clean_text or _caption_info(clean_text):
        return None

    # A direct Word outline level is often accidentally applied to body prose.
    # It must not turn whole paragraphs or research questions into headings.
    if (len(clean_text) > 200 or len(clean_text.split()) > 26
            or re.match(r'^(?:H|RQ)\d+\s*:', clean_text, re.IGNORECASE)
            or (not numbered and clean_text.endswith(('.', '?', '!', ';')))
            or (not numbered and text.rstrip().endswith(':') and not _paragraph_is_all_bold(paragraph))):
        return None

    if numbered:
        return clean_text, numbered[1]

    if _is_heading(paragraph):
        level = _heading_level(paragraph)
        if numbered:
            level = max(level, numbered[1])
        return clean_text, min(3, level)

    if numbered and len(clean_text) <= 120:
        return clean_text, numbered[1]

    is_short = len(clean_text) <= 90 and len(clean_text.split()) <= 12
    sentence_like = clean_text.endswith(('.', '?', '!', ';'))
    numbering_level = _paragraph_numbering_level(paragraph)
    if (numbering_level is not None and is_short and not sentence_like
            and _paragraph_is_all_bold(paragraph)):
        return clean_text, numbering_level
    if is_short and not sentence_like and (
            clean_text.isupper() or _paragraph_is_all_bold(paragraph)):
        return clean_text, 1
    return None


def _para_to_latex(para) -> str:
    """Convert a paragraph with inline formatting to LaTeX."""
    parts = []
    for run in para.runs:
        t = escape(run.text)
        if not t:
            continue
        if run.bold and run.italic:
            t = r'\textbf{\textit{' + t + '}}'
        elif run.bold:
            t = r'\textbf{' + t + '}'
        elif run.italic:
            t = r'\textit{' + t + '}'
        parts.append(t)
    return ''.join(parts)


def _list_to_latex(paras, numbered: bool) -> str:
    env = 'enumerate' if numbered else 'itemize'
    opt = r'[leftmargin=1.2cm, label=\arabic*.]' if numbered else ''
    lines = [r'\begin{' + env + '}' + opt]
    for p in paras:
        lines.append(r'  \item ' + _para_to_latex(p))
    lines.append(r'\end{' + env + '}')
    return '\n'.join(lines)


# ── Word document parser ───────────────────────────────────────────────────────
def extract_from_docx(file_bytes: bytes) -> dict:
    """
    Returns a dict with keys:
      tr_title, en_title, tr_abstract, en_abstract,
      tr_keywords, en_keywords, sections (list of {title, level, latex}),
      references (list of str), raw_paragraphs
    """
    doc = Document(io.BytesIO(file_bytes))
    result = {
        'tr_title': '', 'en_title': '',
        'tr_abstract': '', 'en_abstract': '',
        'tr_keywords': '', 'en_keywords': '',
        'sections': [],
        'references': [],
    }

    paras = [p for p in doc.paragraphs]
    i = 0
    n = len(paras)

    current_section_title = None
    current_section_level = 1
    current_section_lines = []
    in_abstract = False
    in_keywords = False
    abstract_lang = None   # 'tr' or 'en'
    in_references = False

    def flush_section():
        if current_section_title is None:
            return
        result['sections'].append({
            'title': current_section_title,
            'level': current_section_level,
            'latex': '\n\n'.join(current_section_lines),
        })

    # ── first pass: find titles (usually first 1-3 paragraphs before abstract) ──
    first_title_found = False
    for p in paras[:8]:
        txt = _para_text(p)
        if not txt:
            continue
        key = txt.lower().strip().rstrip(':').strip()
        if key in ABSTRACT_KEYS or key in KEYWORD_KEYS:
            break
        if _is_heading(p) or len(txt) > 10:
            if not first_title_found:
                # Heuristic: if line looks like a Turkish title (no ASCII section name)
                if not any(key in txt.lower() for key in SECTION_MAP):
                    result['tr_title'] = escape(txt)
                    first_title_found = True
                    continue
            elif not result['en_title']:
                if not any(key in txt.lower() for key in SECTION_MAP):
                    result['en_title'] = escape(txt)
                    break

    # ── main pass ──
    i = 0
    while i < n:
        para = paras[i]
        txt = _para_text(para)
        key = txt.lower().strip().rstrip(':').strip()
        style = para.style.name

        # Skip empty
        if not txt:
            i += 1
            continue

        # ── References section ──
        if in_references:
            if txt:
                result['references'].append(escape(txt))
            i += 1
            continue

        # ── Heading detection ──
        if _is_heading(para) or (len(txt) < 80 and txt.isupper() and len(txt) > 3):
            mapped = SECTION_MAP.get(key)
            if mapped == '__REFERENCES__':
                flush_section()
                current_section_title = None
                current_section_lines = []
                in_references = True
                i += 1
                continue
            if mapped:
                flush_section()
                current_section_title = mapped
                current_section_level = _heading_level(para) if _is_heading(para) else 1
                current_section_lines = []
                in_abstract = False
                i += 1
                continue
            # Sub-heading inside a known section
            if current_section_title:
                flush_section()
                current_section_title = escape(txt)
                current_section_level = _heading_level(para) if _is_heading(para) else 2
                current_section_lines = []
                i += 1
                continue

        # ── Abstract heading ──
        if key in ABSTRACT_KEYS:
            in_abstract = True
            in_keywords = False
            # determine language from context
            if 'en' in key or key == 'abstract':
                abstract_lang = 'en'
            else:
                abstract_lang = 'tr'
            i += 1
            continue

        # ── Keywords line ──
        if key in KEYWORD_KEYS or txt.lower().startswith('keyword') or txt.lower().startswith('anahtar'):
            in_abstract = False
            in_keywords = True
            # might be on same line: "Keywords: foo, bar"
            colon_pos = txt.find(':')
            if colon_pos != -1:
                kw_val = txt[colon_pos+1:].strip()
                if abstract_lang == 'en':
                    result['en_keywords'] = escape(kw_val)
                else:
                    result['tr_keywords'] = escape(kw_val)
                in_keywords = False
            i += 1
            continue

        if in_keywords:
            if abstract_lang == 'en':
                result['en_keywords'] = escape(txt)
            else:
                result['tr_keywords'] = escape(txt)
            in_keywords = False
            i += 1
            continue

        # ── Abstract body ──
        if in_abstract:
            if abstract_lang == 'en':
                result['en_abstract'] += (' ' if result['en_abstract'] else '') + txt
            else:
                result['tr_abstract'] += (' ' if result['tr_abstract'] else '') + txt
            i += 1
            continue

        # ── Regular paragraph / list ──
        if current_section_title is None:
            i += 1
            continue

        # List paragraph
        if style.startswith('List') or para.style.name in ('List Paragraph', 'Liste Paragrafı'):
            # collect consecutive list items
            list_paras = [para]
            numbered = 'Number' in style or 'Numara' in style
            j = i + 1
            while j < n:
                np2 = paras[j]
                s2 = np2.style.name
                if s2.startswith('List') or s2 in ('List Paragraph',):
                    list_paras.append(np2)
                    j += 1
                else:
                    break
            current_section_lines.append(_list_to_latex(list_paras, numbered))
            i = j
            continue

        # Normal paragraph
        latex_line = _para_to_latex(para)
        if latex_line:
            current_section_lines.append(latex_line)
        i += 1

    flush_section()
    return result


# ── Structured DOCX import for the form UI ───────────────────────────────────
_CAPTION_RE = re.compile(
    r'^\s*(tablo|table|şekil|sekil|figure|fig\.?)\s+(\d+)\s*[:.\-–—]?\s*(.*)$',
    re.IGNORECASE,
)


def _caption_info(text: str) -> dict | None:
    match = _CAPTION_RE.match(text or '')
    if not match:
        return None
    caption = match.group(3).strip()
    # Narrative references such as "Tablo 2'de ..." or "Table 3 shows ..."
    # are not captions. Treating them as captions can replace the actual short
    # caption with a full paragraph and make the table wider than the page.
    if caption.startswith(("'", '’')) or re.match(
            r'^(?:de|da|den|dan|e|a|ye|ya)\b', caption, re.IGNORECASE):
        return None
    if re.match(r'^(?:shows?|göre|görüldüğü|bahsedildiği)\b', caption, re.IGNORECASE):
        return None
    prefix = match.group(1).lower().rstrip('.')
    is_table = prefix in {'tablo', 'table'}
    return {
        'kind': 'table' if is_table else 'figure',
        'lang': 'tr' if prefix in {'tablo', 'şekil', 'sekil'} else 'en',
        'number': match.group(2),
        'caption': caption,
    }


def _paragraph_images(paragraph: Paragraph, document: Document) -> list[dict]:
    images = []
    seen = set()
    for blip in paragraph._p.xpath('.//a:blip | .//*[local-name()="imagedata"]'):
        rel_id = blip.get(qn('r:embed')) or blip.get(qn('r:id'))
        if not rel_id:
            continue
        if rel_id in seen:
            continue
        seen.add(rel_id)
        part = document.part.related_parts.get(rel_id)
        blob = getattr(part, 'blob', None)
        if not blob:
            continue
        filename = os.path.basename(str(getattr(part, 'partname', 'image.png'))) or 'image.png'
        images.append({
            'filename': filename,
            'mimetype': getattr(part, 'content_type', 'application/octet-stream'),
            'bytes': blob,
        })
    return images


def _safe_hex_color(value) -> str:
    value = str(value or '').strip().lstrip('#').upper()
    return value if re.fullmatch(r'[0-9A-F]{6}', value) else ''


def _table_cell_format(cell: _Cell) -> tuple[bool, bool, bool, str, str, str]:
    runs = [run for paragraph in cell.paragraphs for run in paragraph.runs if run.text.strip()]
    bold = bool(runs) and all(run.bold is True for run in runs)
    italic = bool(runs) and all(run.italic is True for run in runs)
    underline = bool(runs) and all(run.underline is True for run in runs)
    alignment = 'left'
    for paragraph in cell.paragraphs:
        if paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            alignment = 'center'
            break
        if paragraph.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
            alignment = 'right'
            break
    shading = cell._tc.tcPr.find(qn('w:shd')) if cell._tc.tcPr is not None else None
    bgcolor = _safe_hex_color(shading.get(qn('w:fill')) if shading is not None else '')
    run_colors = {
        _safe_hex_color(run.font.color.rgb)
        for run in runs if run.font.color is not None and run.font.color.rgb is not None
    }
    run_colors.discard('')
    textcolor = next(iter(run_colors)) if len(run_colors) == 1 else ''
    return bold, italic, underline, alignment, bgcolor, textcolor


def _docx_table_model(table: Table) -> dict:
    """Convert a Word table to the same rich model used by clipboard paste."""
    model_rows: list[list[dict]] = []
    vertical_active: dict[int, dict] = {}

    for tr in table._tbl.tr_lst:
        row_cells: list[dict] = []
        next_vertical: dict[int, dict] = {}
        logical_col = 0

        for tc in tr.tc_lst:
            tc_pr = tc.tcPr
            grid_span = tc_pr.gridSpan
            colspan = int(grid_span.val) if grid_span is not None and grid_span.val else 1
            vmerge = tc_pr.vMerge
            vmerge_value = str(vmerge.val) if vmerge is not None and vmerge.val is not None else ''
            is_continue = vmerge is not None and vmerge_value != 'restart'

            if is_continue and logical_col in vertical_active:
                origin = vertical_active[logical_col]
                origin['rowspan'] = int(origin.get('rowspan', 1)) + 1
                for col in range(logical_col, logical_col + colspan):
                    next_vertical[col] = origin
                logical_col += colspan
                continue

            cell = _Cell(tc, table)
            bold, italic, underline, alignment, bgcolor, textcolor = _table_cell_format(cell)
            paragraphs = [paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip()]
            cell_data = {
                'text': '\n'.join(paragraphs),
                'colspan': max(1, colspan),
                'rowspan': 1,
                'bold': bold,
                'italic': italic,
                'underline': underline,
                'align': alignment,
                'bgcolor': bgcolor,
                'textcolor': textcolor,
            }
            row_cells.append(cell_data)

            if vmerge is not None and vmerge_value == 'restart':
                for col in range(logical_col, logical_col + colspan):
                    next_vertical[col] = cell_data
            logical_col += colspan

        model_rows.append(row_cells)
        vertical_active = next_vertical

    widths = []
    tbl_grid = table._tbl.tblGrid
    if tbl_grid is not None:
        for grid_col in tbl_grid.gridCol_lst:
            try:
                widths.append(max(1.0, float(grid_col.w)))
            except (TypeError, ValueError):
                widths = []
                break

    ncols = max(
        len(widths),
        max((sum(int(cell.get('colspan', 1)) for cell in row) for row in model_rows), default=1),
    )
    if len(widths) != ncols:
        widths = [1.0] * ncols
    width_sum = sum(widths) or 1.0
    normalized_widths = [width / width_sum for width in widths]

    explicit_header_rows = 0
    for tr in table._tbl.tr_lst:
        tr_pr = tr.trPr
        is_header = tr_pr is not None and tr_pr.find(qn('w:tblHeader')) is not None
        if not is_header:
            break
        explicit_header_rows += 1
    header_rows = explicit_header_rows or (1 if len(model_rows) > 1 else 0)
    has_grid_borders = bool(
        table._tbl.xpath('./w:tblPr/w:tblBorders | .//w:tcPr/w:tcBorders')
    ) or 'grid' in (table.style.name.lower() if table.style is not None else '')

    return {
        'rows': model_rows or [[{'text': ''}]],
        'column_widths': normalized_widths,
        'header_rows': header_rows,
        'grid_borders': has_grid_borders,
    }


def _table_requires_page_split(model: dict) -> bool:
    """Estimate whether a Word table is too tall for a single-page float."""
    rows = model.get('rows', []) if isinstance(model, dict) else []
    widths = model.get('column_widths', []) if isinstance(model, dict) else []
    if len(rows) > 18:
        return True
    estimated_lines = 0
    for row in rows:
        row_lines = 1
        logical_col = 0
        for cell in row:
            colspan = _bounded_int(cell.get('colspan'), 1, 50)
            width_fraction = sum(widths[logical_col:logical_col + colspan]) if widths else 1 / max(1, len(row))
            chars_per_line = max(12, int(105 * max(0.08, width_fraction)))
            text_lines = str(cell.get('text', '')).splitlines() or ['']
            wrapped_lines = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line) for line in text_lines)
            row_lines = max(row_lines, wrapped_lines)
            logical_col += colspan
        estimated_lines += row_lines
    return estimated_lines > 30


def _docx_blocks(document: Document) -> tuple[list[dict], list[dict]]:
    blocks: list[dict] = []
    images: list[dict] = []
    # Keep references to the XML nodes themselves. Storing only id(node) lets
    # Python recycle proxy ids while the document is being walked, which made
    # paragraph/heading extraction nondeterministic on large manuscripts.
    seen_paragraphs: set[CT_P] = set()
    body_started = False

    def append_paragraph(paragraph: Paragraph):
        element = paragraph._p
        if element in seen_paragraphs:
            return
        seen_paragraphs.add(element)
        text = paragraph.text.strip()
        if text:
            blocks.append({
                'kind': 'paragraph',
                'text': text,
                'paragraph': paragraph,
                'style': paragraph.style.name if paragraph.style else '',
            })
        for image in _paragraph_images(paragraph, document):
            image_index = len(images)
            images.append(image)
            blocks.append({
                'kind': 'figure',
                'image_index': image_index,
                'filename': image['filename'],
                'mimetype': image['mimetype'],
            })

        # Word text boxes are stored inside drawing elements and are omitted
        # by python-docx's normal paragraph iterator. Recover their paragraphs
        # so template-based abstracts are not silently lost.
        nested = paragraph._p.xpath('.//w:txbxContent//w:p')
        # Figure text is not article prose. Word-native diagrams require an
        # image export; expose that limitation to the user instead of creating
        # dozens of spurious sections from flowchart labels.
        if not body_started or any(_abstract_label_info(''.join(p.itertext())) for p in nested):
            seen_text = set()
            for nested_p in nested:
                p = Paragraph(nested_p, paragraph._parent)
                if p.text not in seen_text:
                    append_paragraph(p)
                    seen_text.add(p.text)

    def iter_block_elements(parent):
        """Yield paragraphs/tables inside body content controls in order."""
        for child in parent.iterchildren():
            if isinstance(child, (CT_P, CT_Tbl)):
                yield child
            else:
                yield from iter_block_elements(child)

    for child in iter_block_elements(document.element.body):
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, document)
            append_paragraph(paragraph)
            text = paragraph.text.strip()
            if text:
                numbered = _numbered_section_title(text)
                lookup_text = numbered[0] if numbered else text
                key = lookup_text.lower().strip().rstrip(':').strip()
                is_body_heading = (
                    SECTION_MAP.get(key) not in {None, '__REFERENCES__'}
                    or bool(_dynamic_section_heading(text, paragraph))
                )
                if is_body_heading and not (
                    _abstract_label_info(text) or _keyword_label_info(text)
                    or _is_article_type_text(text)
                ):
                    body_started = True
                if _caption_info(text):
                    body_started = True
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            table_paragraphs = [
                paragraph
                for row in table.rows
                for cell in row.cells
                for paragraph in cell.paragraphs
                if paragraph.text.strip()
            ]
            # Journal templates often put the complete title/abstract area in
            # a large borderless layout table. Any table carrying front-matter
            # labels is therefore flattened, regardless of its cell count.
            abstract_languages = {
                info[0]
                for paragraph in table_paragraphs
                if (info := _abstract_label_info(paragraph.text.strip()))
            }
            keyword_languages = {
                info[0]
                for paragraph in table_paragraphs
                if (info := _keyword_label_info(paragraph.text.strip()))
            }
            has_front_matter_label = bool(abstract_languages or keyword_languages)
            strong_front_matter_layout = (
                len(abstract_languages) >= 2
                or bool(abstract_languages and keyword_languages)
            )
            is_front_matter_table = has_front_matter_label and (
                not body_started or strong_front_matter_layout
            )
            if is_front_matter_table:
                for paragraph in table_paragraphs:
                    append_paragraph(paragraph)
                continue
            blocks.append({'kind': 'table', 'model': _docx_table_model(table)})

    return blocks, images


def _looks_like_front_matter(text: str) -> bool:
    lower = text.lower()
    return bool(
        '@' in text or re.search(r'\b\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b', text)
        or _is_front_matter_metadata_text(text)
        or any(token in lower for token in (
            'üniversite', 'university', 'fakülte', 'faculty', 'department',
            'bölümü', 'enstitü', 'institute', 'orcid', 'issn', 'http://',
            'https://', 'doi:', 'year:', 'volume:', 'issue:', 'yıl:',
            'cilt:', 'sayı:', 'journal of global tourism and technology research',
        ))
    )


_FRONT_MATTER_METADATA_RE = re.compile(
    r'^\s*(?:makale\s+bilgisi|article\s+info|makale\s+geçmişi|background|'
    r'başvuru\s+tarihi|received|kabul\s+tarihi|accepted|yayın\s+tarihi|published)'
    r'(?:\s*:\s*.*|\s+\d.*|\s*)$',
    re.IGNORECASE,
)


def _is_front_matter_metadata_text(text: str) -> bool:
    return bool(_FRONT_MATTER_METADATA_RE.match(text or ''))


_ARTICLE_TYPE_RE = re.compile(
    r'^\s*(?:(?:araştırma|derleme|olgu|vaka)\s+makalesi|'
    r'research\s+article|review\s+article|original\s+article|case\s+report)'
    r'(?:\s*[-–—/]\s*(?:research|review|original)\s+article)?\s*$',
    re.IGNORECASE,
)


def _is_article_type_text(text: str) -> bool:
    return bool(_ARTICLE_TYPE_RE.match(text or ''))


def _paragraph_is_list(paragraph: Paragraph) -> bool:
    style = paragraph.style.name if paragraph.style else ''
    if style.startswith('List') or style.startswith('Liste'):
        return True
    p_pr = paragraph._p.pPr
    return p_pr is not None and p_pr.numPr is not None


def extract_form_data_from_docx(file_bytes: bytes) -> tuple[dict, list[dict]]:
    """Extract a reviewable form payload and body images from a DOCX file."""
    document = Document(io.BytesIO(file_bytes))
    blocks, images = _docx_blocks(document)
    paragraph_indices = [index for index, block in enumerate(blocks) if block['kind'] == 'paragraph']

    special_start = len(blocks)
    for index in paragraph_indices:
        text = blocks[index]['text']
        if _is_article_type_text(text):
            continue
        numbered = _numbered_section_title(text)
        lookup_text = numbered[0] if numbered else text
        key = lookup_text.lower().strip().rstrip(':').strip()
        if (_abstract_label_info(text) or _keyword_label_info(text)
                or key in ABSTRACT_KEYS or key in KEYWORD_KEYS or key in SECTION_MAP
                or text.lower().startswith(('anahtar kelime', 'anahtar sözcük', 'keywords'))
                or numbered or _is_heading(blocks[index]['paragraph'])):
            special_start = index
            break

    title_candidates = []
    for index in paragraph_indices:
        if index >= special_start:
            break
        text = blocks[index]['text']
        if (len(text) < 8 or _looks_like_front_matter(text)
                or _caption_info(text) or _is_article_type_text(text)):
            continue
        style_lower = blocks[index]['style'].lower()
        is_title_style = 'title' in style_lower or 'başlık' in style_lower
        if not is_title_style and (
                len(text) > 260 or len(text.split()) > 28
                or text.rstrip().endswith(('.', ';', '!', '?'))):
            continue
        priority = 0 if is_title_style else 1
        title_candidates.append((priority, index, text))

    title_candidates.sort(key=lambda item: (item[0], item[1]))
    selected_titles = sorted(title_candidates[:2], key=lambda item: item[1])
    title_indices = {item[1] for item in selected_titles}
    tr_title = selected_titles[0][2] if selected_titles else ''
    en_title = selected_titles[1][2] if len(selected_titles) > 1 else ''

    # Many manuscripts put the English title between the Turkish keywords and
    # Abstract; title paragraphs can also carry erroneous outline formatting.
    labeled_titles = {}
    labeled_title_indices = set()
    for pos, index in enumerate(paragraph_indices):
        info = _abstract_label_info(blocks[index]['text'])
        if not info or info[1] or pos == 0:
            continue
        previous = paragraph_indices[pos - 1]
        text = blocks[previous]['text']
        if (8 <= len(text) <= 400 and len(text.split()) <= 45
                and not _keyword_label_info(text) and not _abstract_label_info(text)
                and '@' not in text and not _is_front_matter_metadata_text(text)
                and not _is_article_type_text(text) and ';' not in text
                and not text.endswith(('.', ';'))):
            labeled_titles[info[0]] = text
            labeled_title_indices.add(previous)
    if labeled_titles and len(selected_titles) < 2:
        tr_title = labeled_titles.get('tr', '')
        en_title = labeled_titles.get('en', '')
        title_indices.update(labeled_title_indices)

    captions_by_target: dict[int, dict] = {}
    caption_indices: set[int] = set()
    claimed_caption_indices: set[int] = set()
    for target_index, block in enumerate(blocks):
        if block['kind'] not in {'table', 'figure'}:
            continue
        caption_data = {'tr_cap': '', 'en_cap': '', 'number': ''}
        candidates = []
        # Word conventionally places table captions above and figure captions
        # below. Prefer that side so a caption between two objects is not
        # accidentally assigned to both.
        directions = (-1, 1) if block['kind'] == 'table' else (1, -1)
        for direction in directions:
            side_candidates = []
            cursor = target_index + direction
            checked = 0
            while 0 <= cursor < len(blocks) and checked < 2:
                nearby = blocks[cursor]
                if nearby['kind'] != 'paragraph' or cursor in claimed_caption_indices:
                    break
                info = _caption_info(nearby['text'])
                if not info or info['kind'] != block['kind']:
                    break
                side_candidates.append((cursor, info))
                cursor += direction
                checked += 1
            if side_candidates:
                # Once a caption is found on the conventional side, do not
                # let narrative text on the opposite side overwrite it.
                candidates = side_candidates
                break
        for caption_index, info in sorted(candidates, key=lambda item: item[0]):
            caption_data['tr_cap' if info['lang'] == 'tr' else 'en_cap'] = info['caption']
            caption_data['number'] = caption_data['number'] or info['number']
            caption_indices.add(caption_index)
            claimed_caption_indices.add(caption_index)
        captions_by_target[target_index] = caption_data

    result = {
        'cover': {'tr_title': tr_title, 'en_title': en_title},
        'abstract': {'tr_abs': '', 'tr_kw': '', 'en_abs': '', 'en_kw': ''},
        'sections': [],
        'figtables': [],
        'extra': {'ack': '', 'contrib': '', 'conflict': ''},
        'references': '',
        'warnings': [],
        'stats': {},
    }
    current_section: dict | None = None
    abstract_lang: str | None = None
    keyword_lang: str | None = None
    optional_endmatter_field: str | None = None
    front_matter_complete = False
    front_candidates: list[tuple[int, str, Paragraph]] = []
    consumed_front_candidates: set[int] = set()
    in_references = False
    references: list[str] = []
    table_number = 0
    figure_number = 0

    def create_section(name: str, level: int = 1) -> dict:
        section = {'id': str(len(result['sections'])), 'name': name, 'level': str(max(1, min(level, 3))), '_paragraphs': []}
        result['sections'].append(section)
        return section

    def fill_abstract_from_front_candidates(lang: str):
        field = lang + '_abs'
        if result['abstract'][field]:
            return
        matching = [
            (candidate_index, candidate_text)
            for candidate_index, candidate_text, _ in front_candidates
            if candidate_index not in consumed_front_candidates
            and len(candidate_text.split()) >= 12
            and _guess_text_language(candidate_text) == lang
        ]
        if not matching:
            return
        # The closest prose block before its keyword line is normally the
        # abstract. Retain adjacent same-language blocks for structured prose.
        selected = matching[-3:]
        result['abstract'][field] = ' '.join(text for _, text in selected)
        consumed_front_candidates.update(index for index, _ in selected)

    for index, block in enumerate(blocks):
        kind = block['kind']

        if kind in {'table', 'figure'}:
            anchor = (
                current_section['_paragraphs'][-1]
                if current_section is not None and current_section['_paragraphs'] else ''
            )
            caption = captions_by_target.get(index, {})
            if kind == 'table':
                table_number += 1
                number = caption.get('number') or str(table_number)
                ncols = len(block['model'].get('column_widths', []))
                item = {
                    'type': 'table',
                    'tbl_model': block['model'],
                    'split_table': _table_requires_page_split(block['model']),
                    'tbl_fontsize': '8.5' if ncols > 6 else '',
                }
            else:
                figure_number += 1
                number = caption.get('number') or str(figure_number)
                item = {
                    'type': 'figure',
                    'import_image_index': block['image_index'],
                    'filename': block['filename'],
                    'mimetype': block['mimetype'],
                }
            item.update({
                'number': number,
                'tr_cap': caption.get('tr_cap', ''),
                'en_cap': caption.get('en_cap', ''),
                'section': current_section['name'] if current_section is not None else '',
                'section_id': current_section['id'] if current_section is not None else None,
                'after_para': anchor,
                'placement': '' if anchor else 'section_start',
            })
            result['figtables'].append(item)
            continue

        text = block['text']
        numbered = _numbered_section_title(text)
        lookup_text = numbered[0] if numbered else text
        key = lookup_text.lower().strip().rstrip(':').strip()
        if index in title_indices or index in caption_indices:
            continue

        if not result['sections'] and not in_references and not abstract_lang and _is_article_type_text(text):
            result['cover']['article_type'] = text
            continue

        # These labels also occur in genuine abstracts, body headings and
        # reference author names. Only discard metadata in the cover area.
        if (not result['sections'] and not in_references and not abstract_lang
                and not front_matter_complete and _is_front_matter_metadata_text(text)):
            continue

        if in_references:
            references.append(text)
            continue

        mapped = SECTION_MAP.get(key)
        if mapped == '__REFERENCES__':
            in_references = True
            optional_endmatter_field = None
            abstract_lang = keyword_lang = None
            continue

        optional_field = OPTIONAL_END_MATTER_MAP.get(key)
        if optional_field:
            optional_endmatter_field = optional_field
            current_section = None
            abstract_lang = keyword_lang = None
            continue

        abstract_info = _abstract_label_info(text)
        if abstract_info:
            abstract_lang, abstract_value = abstract_info
            keyword_lang = None
            current_section = None
            if abstract_value:
                field = abstract_lang + '_abs'
                result['abstract'][field] += (
                    (' ' if result['abstract'][field] else '') + abstract_value
                )
            continue

        keyword_info = _keyword_label_info(text)
        if keyword_info:
            keyword_lang, value = keyword_info
            if value:
                result['abstract'][keyword_lang + '_kw'] = value
                fill_abstract_from_front_candidates(keyword_lang)
                keyword_lang = None
            abstract_lang = None
            front_matter_complete = True
            continue

        if keyword_lang:
            result['abstract'][keyword_lang + '_kw'] = text
            fill_abstract_from_front_candidates(keyword_lang)
            keyword_lang = None
            front_matter_complete = True
            continue

        heading_info = _dynamic_section_heading(text, block['paragraph'])
        # Bold "Purpose"/"Methods" labels can belong to a structured abstract.
        # Without keywords, require explicit heading structure to start the body.
        ends_abstract = (
            (heading_info and (numbered or _is_heading(block['paragraph'])))
            or (mapped and _is_heading(block['paragraph']))
        )
        if abstract_lang and not ends_abstract:
            field = abstract_lang + '_abs'
            result['abstract'][field] += (' ' if result['abstract'][field] else '') + text
            continue

        style_abstract_lang = _abstract_style_language(block['paragraph'], text)
        if style_abstract_lang and not mapped:
            field = style_abstract_lang + '_abs'
            result['abstract'][field] += (' ' if result['abstract'][field] else '') + text
            continue

        if optional_endmatter_field and not (mapped or heading_info):
            existing = result['extra'][optional_endmatter_field]
            result['extra'][optional_endmatter_field] = (
                existing + ('\n\n' if existing else '') + text
            )
            continue

        if mapped or heading_info:
            optional_endmatter_field = None
            section_name, section_level = heading_info or (lookup_text, 1)
            # Preserve the document's own section name. SECTION_MAP is used to
            # identify standard/reference headings, not to force a fixed list.
            current_section = create_section(section_name, section_level)
            abstract_lang = keyword_lang = None
            continue

        if current_section is None:
            if not _looks_like_front_matter(text) and len(text.split()) >= 8:
                front_candidates.append((index, text, block['paragraph']))
            continue

        if current_section is not None:
            paragraph_text = ('• ' + text) if _paragraph_is_list(block['paragraph']) else text
            current_section['_paragraphs'].append(paragraph_text)

    for section in result['sections']:
        section['content'] = '\n\n'.join(section.pop('_paragraphs'))

    # If no headings exist at all, retain unclaimed prose as a generic body
    # instead of mistaking it for a template section or silently dropping it.
    unclaimed_body = [
        text for candidate_index, text, _ in front_candidates
        if candidate_index not in consumed_front_candidates
    ]
    if not result['sections'] and unclaimed_body and front_matter_complete:
        result['sections'].append({
            'name': 'Makale Metni / Article Body',
            'level': '1',
            'content': '\n\n'.join(unclaimed_body),
        })
    result['references'] = '\n'.join(references)

    if not (result['cover']['tr_title'] or result['cover']['en_title']):
        result['warnings'].append('Makale başlığı güvenilir biçimde belirlenemedi; kapak alanını kontrol edin.')
    native_graphics = document.element.xpath('.//*[local-name()="chart"] | .//w:txbxContent')
    if native_graphics:
        result['warnings'].append('Word çizimleri, grafikler veya metin kutuları bulundu. Görsel olmayan Word şekilleri otomatik resme dönüştürülemez; şekilleri Word’den PNG/JPG olarak kaydedip şekil alanından ekleyin ve konumlarını kontrol edin.')
    if not result['sections']:
        result['warnings'].append('Word dosyasında güvenilir biçimde belirlenebilen makale bölümü bulunamadı.')
    result['warnings'].append('Yazar, tarih, DOI ve sayı bilgileri Word dosyasından güvenilir biçimde çıkarılamadığı için mevcut alanlar korundu.')
    result['stats'] = {
        'sections': len(result['sections']),
        'tables': table_number,
        'figures': figure_number,
        'references': len(references),
    }
    return result, images


# ── Author info parser ─────────────────────────────────────────────────────────
def parse_author_info(file_bytes: bytes, filename: str) -> list:
    """
    Parse author info from a .docx or .txt file.
    Expected format (one author per line/paragraph):
      Ad Soyad | Kurum | ORCID | email | sorumlu(evet/hayır)
    or Word table with columns: Ad Soyad, Kurum, ORCID, E-posta, Sorumlu
    Returns list of dicts.
    """
    authors = []

    if filename.lower().endswith('.docx'):
        doc = Document(io.BytesIO(file_bytes))
        # Try table first
        if doc.tables:
            tbl = doc.tables[0]
            for row in tbl.rows[1:]:  # skip header
                cells = [c.text.strip() for c in row.cells]
                if len(cells) >= 4 and cells[0]:
                    authors.append({
                        'name':        cells[0],
                        'affiliation': cells[1] if len(cells) > 1 else '',
                        'orcid':       cells[2] if len(cells) > 2 else '',
                        'email':       cells[3] if len(cells) > 3 else '',
                        'corresponding': len(cells) > 4 and cells[4].lower() in ('evet', 'yes', 'e', 'y', '1', 'true'),
                    })
        else:
            for para in doc.paragraphs:
                txt = para.text.strip()
                if not txt or txt.startswith('#'):
                    continue
                parts = [p.strip() for p in re.split(r'[|\t;]', txt)]
                if len(parts) >= 2:
                    authors.append({
                        'name':        parts[0],
                        'affiliation': parts[1] if len(parts) > 1 else '',
                        'orcid':       parts[2] if len(parts) > 2 else '',
                        'email':       parts[3] if len(parts) > 3 else '',
                        'corresponding': len(parts) > 4 and parts[4].lower() in ('evet', 'yes', 'e', 'y', '1', 'true'),
                    })
    else:
        # Plain text
        text = file_bytes.decode('utf-8', errors='ignore')
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in re.split(r'[|\t;]', line)]
            if len(parts) >= 2:
                authors.append({
                    'name':        parts[0],
                    'affiliation': parts[1] if len(parts) > 1 else '',
                    'orcid':       parts[2] if len(parts) > 2 else '',
                    'email':       parts[3] if len(parts) > 3 else '',
                    'corresponding': len(parts) > 4 and parts[4].lower() in ('evet', 'yes', 'e', 'y', '1', 'true'),
                })

    return authors


# ── LaTeX generation ───────────────────────────────────────────────────────────

def _format_author_block(authors: list, corr_marker: str = '*') -> str:
    parts = []
    marker_tex = _latex_marker(corr_marker)
    for idx, a in enumerate(authors, 1):
        sup = str(idx)
        if a.get('corresponding'):
            sup += ',' + marker_tex
        orcid = _clean_orcid(a.get('orcid', ''))
        orcid_part = r'\,\orcidlink{' + orcid + '}' if orcid else ''
        # Title (Ünvan) — opsiyonel, varsa ad-soyad'ın önüne eklenir
        title = a.get('title', '').strip()
        author_name = a.get('name', '').strip()
        name_with_title = (escape(title) + r'~' + escape(author_name)) if title else escape(author_name)
        parts.append(name_with_title + r'\textsuperscript{' + sup + r'}' + orcid_part)
    return ',\n  '.join(parts)


def _format_affiliations(authors: list, english_only: bool = False) -> str:
    lines = []
    email_label = 'E-mail: ' if english_only else 'E-posta: '
    for idx, a in enumerate(authors, 1):
        orcid = _clean_orcid(a.get('orcid', ''))
        email = a.get('email', '').strip()
        orcid_part = r' ORCID: \href{https://orcid.org/' + orcid + r'}{\mbox{' + orcid + r'}}.' if orcid else ''
        email_part = (r' ' + email_label + r'\href{' + _url_target('mailto:' + email) + r'}{\mbox{' + escape(email) + r'}}') if email else ''
        lines.append(
            r'\textsuperscript{' + str(idx) + r'}' +
            escape(a.get('affiliation', '')) + '.' +
            orcid_part + email_part
        )
    return (r'\\' + '\n  ').join(lines)


def _format_corresponding(authors: list, english_only: bool = False) -> str:
    email_label = 'E-mail: ' if english_only else 'E-posta: '
    for a in authors:
        if a.get('corresponding'):
            name  = escape(a.get('name', ''))
            email = a.get('email', '')
            aff   = escape(a.get('affiliation', ''))
            ep    = r'. ' + email_label + r'\href{' + _url_target('mailto:' + email) + r'}{' + escape(email) + r'}' if email else ''
            return name + (', ' + aff if aff else '') + ep
    if authors:
        a = authors[0]
        name  = escape(a.get('name', ''))
        email = a.get('email', '')
        ep    = r'. ' + email_label + r'\href{' + _url_target('mailto:' + email) + r'}{' + escape(email) + r'}' if email else ''
        return name + ep
    return 'Author Name, Institution' if english_only else 'Yazar Adı, Kurum, E-posta'


# ── First-page LaTeX builder helpers ─────────────────────────────────────────
def _build_meta_strip(english_only: bool) -> str:
    """Sayfanın üst kısmındaki Yıl/Cilt/Sayı şeridi."""
    if english_only:
        return (r'{\fontsize{8}{10}\selectfont\quad Year: \JGTTRyear\quad '
                r'Volume: \JGTTRvolume\quad Issue: \JGTTRissue\quad}')
    return (r'{\fontsize{8}{10}\selectfont\quad Year: \JGTTRyear\quad '
            r'Volume: \JGTTRvolume\quad Issue: \JGTTRissue%'
            '\n       '
            r'\hfill Yıl: \JGTTRyear\quad Cilt: \JGTTRvolume\quad '
            r'Sayı: \JGTTRissue\quad}')


def _build_corresponding_label(english_only: bool, marker: str) -> str:
    """Dipnot satırındaki sorumlu yazar etiketi."""
    if english_only:
        return marker + r' Corresponding author'
    return marker + r' Sorumlu yazar / Corresponding author'


def _build_editor_row(editor: str, english_only: bool) -> str:
    """Sol sütunda anahtar kelimelerin altına eklenen opsiyonel 'İlgilenen Editör' satırı."""
    if not editor:
        return ''
    label = 'Editor:' if english_only else 'Editör / Editor:'
    return (
        '\n'
        r'      \vspace{2pt}\inforule%' + '\n'
        r'      \infoboldlabel{' + label + r'}\par\inforule%' + '\n'
        r'      \infovalue{' + escape(editor) + r'}\vspace{2pt}%'
    )


def _build_abstract_block(english_only: bool, has_tr: bool, has_en: bool, editor: str = '') -> str:
    """Özet/Abstract iki sütunlu blok. Boşsa ilgili sütunu gizler.

    English-only modunda yalnızca İngilizce blok gösterilir.
    """
    editor_row = _build_editor_row(editor, english_only)
    # English-only: tek sütun, sadece İngilizce
    if english_only:
        if not has_en:
            return ''
        return (
            r'\noindent\begin{minipage}[t]{\textwidth}%' + '\n'
            r'  \setlength{\parindent}{0pt}\setlength{\parskip}{0pt}\vspace{0pt}%' + '\n'
            r'  \begin{tabular}{@{} p{0.183\textwidth} @{\hspace{2pt}} p{0.797\textwidth} @{}}%' + '\n'
            r'    \begin{minipage}[t]{0.183\textwidth}%' + '\n'
            r'      \setlength{\parindent}{0pt}\setlength{\parskip}{0pt}\vspace{0pt}%' + '\n'
            r'      \centering\infolabel{ARTICLE INFO}\par\inforule%' + '\n'
            r'      \infosubheading{Background:}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Received: \JGTTRreceived}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Accepted: \JGTTRaccepted}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Published: \JGTTRpublished}\par\inforule%' + '\n'
            r'      \infoboldlabel{Keywords:}\par\inforule%' + '\n'
            r'      \infovalue{\JGTTRenglishkeywords}\vspace{2pt}%' + editor_row + '\n'
            r'    \end{minipage}%' + '\n'
            r'    &%' + '\n'
            r'    \begin{minipage}[t]{0.797\textwidth}%' + '\n'
            r'      \setlength{\parindent}{0pt}\setlength{\parskip}{0pt}\vspace{0pt}%' + '\n'
            r'      {\fontsize{8.5}{10.5}\selectfont\bfseries\scshape Abstract}\par%' + '\n'
            r'      \noindent\rule{\linewidth}{0.4pt}\par%' + '\n'
            r'      {\fontsize{8.5}{10.5}\selectfont\JGTTRenglishabstract}\vspace{2pt}%' + '\n'
            r'    \end{minipage}%' + '\n'
            r'  \end{tabular}%' + '\n'
            r'\end{minipage}%'
        )

    # İki dilli — TR ve/veya EN bloklarını koşullu çıkar
    blocks = []

    if has_tr:
        blocks.append(
            r'    \begin{minipage}[t]{0.183\textwidth}%' + '\n'
            r'      \setlength{\parindent}{0pt}\setlength{\parskip}{0pt}\vspace{0pt}%' + '\n'
            r'      \centering\infolabel{MAKALE BİLGİSİ}\par\inforule%' + '\n'
            r'      \infosubheading{Makale Geçmişi:}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Baş. tarihi: \JGTTRreceived}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Kabul tarihi: \JGTTRaccepted}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Yayın tarihi: \JGTTRpublished}\par\inforule%' + '\n'
            r'      \infoboldlabel{Anahtar Kelimeler:}\par\inforule%' + '\n'
            r'      \infovalue{\JGTTRturkishkeywords}\vspace{2pt}%' + editor_row + '\n'
            r'    \end{minipage}%' + '\n'
            r'    &%' + '\n'
            r'    \begin{minipage}[t]{0.797\textwidth}%' + '\n'
            r'      \setlength{\parindent}{0pt}\setlength{\parskip}{0pt}\vspace{0pt}%' + '\n'
            r'      {\fontsize{8.5}{10.5}\selectfont\bfseries\scshape Öz}\par%' + '\n'
            r'      \noindent\rule{\linewidth}{0.4pt}\par%' + '\n'
            r'      {\fontsize{8.5}{10.5}\selectfont\JGTTRturkishabstract}\vspace{2pt}%' + '\n'
            r'    \end{minipage}%'
        )

    if has_en:
        blocks.append(
            r'    \begin{minipage}[t]{0.183\textwidth}%' + '\n'
            r'      \setlength{\parindent}{0pt}\setlength{\parskip}{0pt}\vspace{0pt}%' + '\n'
            r'      \centering\infolabel{ARTICLE INFO}\par\inforule%' + '\n'
            r'      \infosubheading{Background:}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Received: \JGTTRreceived}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Accepted: \JGTTRaccepted}\par\inforule%' + '\n'
            r'      {\fontsize{7.5}{9}\selectfont Published: \JGTTRpublished}\par\inforule%' + '\n'
            r'      \infoboldlabel{Keywords:}\par\inforule%' + '\n'
            r'      \infovalue{\JGTTRenglishkeywords}\vspace{2pt}%' + editor_row + '\n'
            r'    \end{minipage}%' + '\n'
            r'    &%' + '\n'
            r'    \begin{minipage}[t]{0.797\textwidth}%' + '\n'
            r'      \setlength{\parindent}{0pt}\setlength{\parskip}{0pt}\vspace{0pt}%' + '\n'
            r'      {\fontsize{8.5}{10.5}\selectfont\bfseries\scshape Abstract}\par%' + '\n'
            r'      \noindent\rule{\linewidth}{0.4pt}\par%' + '\n'
            r'      {\fontsize{8.5}{10.5}\selectfont\JGTTRenglishabstract}\vspace{2pt}%' + '\n'
            r'    \end{minipage}%'
        )

    if not blocks:
        return ''

    sep = (r'    \\[3pt]%' + '\n'
           r'    \multicolumn{2}{@{}l@{}}{\rule{\dimexpr0.183\textwidth+0.797\textwidth+8pt\relax}{0.4pt}}\\[2pt]%' + '\n')

    body = blocks[0]
    for b in blocks[1:]:
        body += '\n' + sep + b
    body += r'\\[0pt]%'

    return (
        r'\noindent%' + '\n'
        r'\begin{tabular}{@{} p{0.183\textwidth} @{\hspace{2pt}} p{0.797\textwidth} @{}}%' + '\n'
        + body + '\n'
        r'\end{tabular}%'
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FORM-BASED LaTeX GENERATION
# ══════════════════════════════════════════════════════════════════════════════

SECTION_CMD_MAP = {'1': r'\section', '2': r'\subsection', '3': r'\subsubsection'}

# Special starred sections (no numbering)
STARRED_NAMES = {
    'araştırmacı', 'katkı', 'contributions', 'çıkar', 'conflict',
    'teşekkür', 'acknowledgement', 'kaynakça', 'references', 'bibliography',
}


def _is_markdown_separator(row: list[str]) -> bool:
    return bool(row) and all(re.fullmatch(r':?-{3,}:?', c.strip()) for c in row if c.strip())


def _parse_table_rows(text: str) -> list[list[str]]:
    """Parse pasted table text from pipe, Excel/Word TSV, or simple CSV input."""
    normalized = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    # Keep leading/trailing tabs: they represent empty Word/Excel edge cells.
    lines = [line for line in normalized.split('\n') if line.strip()]
    if not lines:
        return []

    if any('\t' in line for line in lines):
        rows = [[cell.strip() for cell in line.split('\t')] for line in lines]
    elif any('|' in line for line in lines):
        rows = []
        for line in lines:
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if not _is_markdown_separator(cells):
                rows.append(cells)
    else:
        try:
            sample = '\n'.join(lines[:5])
            dialect = csv.Sniffer().sniff(sample, delimiters=',;')
            rows = [[cell.strip() for cell in row] for row in csv.reader(lines, dialect)]
        except csv.Error:
            rows = [[line] for line in lines]

    return [row for row in rows if any(cell.strip() for cell in row)]


def _table_to_latex(text: str) -> tuple:
    """Parse plain Word/Excel TSV, Markdown or CSV into safe table components."""
    rows = [[escape(cell) for cell in row] for row in _parse_table_rows(text)]
    if not rows:
        return 'l', [], [], 1
    ncols = max(len(row) for row in rows)
    for row in rows:
        row.extend([''] * (ncols - len(row)))
    return 'l' * ncols, rows[0], rows[1:], ncols


def _bounded_int(value, default: int = 1, maximum: int = 100) -> int:
    """Return a positive, bounded integer for untrusted table span values."""
    try:
        return max(1, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def _cell_alignment(value) -> str:
    value = str(value or '').lower()
    return value if value in {'left', 'center', 'right'} else 'left'


def _layout_table_rows(rows: list) -> tuple[list, int]:
    """Assign logical column positions while respecting row and column spans."""
    active_rowspans: list[int] = []
    laid_out = []
    ncols = 1

    for row in rows:
        entries = []
        col = 0
        for cell in row:
            while col < len(active_rowspans) and active_rowspans[col] > 0:
                col += 1
            colspan = _bounded_int(cell.get('colspan'), 1, 50)
            rowspan = _bounded_int(cell.get('rowspan'), 1, 100)
            needed = col + colspan
            if needed > 50:
                raise ValueError('Tablo 50 sütundan geniş; daha dar tablolara ayırın.')
            if needed > len(active_rowspans):
                active_rowspans.extend([0] * (needed - len(active_rowspans)))
            entries.append({'col': col, 'colspan': colspan, 'rowspan': rowspan, 'cell': cell})
            for idx in range(col, needed):
                active_rowspans[idx] = max(active_rowspans[idx], rowspan)
            col = needed

        ncols = max(ncols, col, len(active_rowspans))
        laid_out.append(entries)
        active_rowspans = [max(0, span - 1) for span in active_rowspans]

    return laid_out, ncols


def _normalize_table_model(ft: dict) -> dict:
    """Normalize rich clipboard tables, falling back to the legacy pipe format."""
    raw_model = ft.get('tbl_model')
    raw_rows = raw_model.get('rows') if isinstance(raw_model, dict) else None
    rows = []

    if isinstance(raw_rows, list) and raw_rows:
        if len(raw_rows) > 500:
            raise ValueError('Tablo 500 satırdan uzun; veri kaybını önlemek için tabloyu bölün.')
        for raw_row in raw_rows:
            if not isinstance(raw_row, list):
                raise ValueError('Her tablo satırı bir hücre listesi olmalıdır.')
            if len(raw_row) > 100:
                raise ValueError('Tablo satırı çok geniş; tabloyu daha dar parçalara bölün.')
            row = []
            for raw_cell in raw_row:
                if not isinstance(raw_cell, dict):
                    raw_cell = {'text': str(raw_cell or '')}
                row.append({
                    'text': str(raw_cell.get('text', '')),
                    'colspan': _bounded_int(raw_cell.get('colspan'), 1, 50),
                    'rowspan': _bounded_int(raw_cell.get('rowspan'), 1, 100),
                    'bold': bool(raw_cell.get('bold')),
                    'italic': bool(raw_cell.get('italic')),
                    'underline': bool(raw_cell.get('underline')),
                    'align': _cell_alignment(raw_cell.get('align')),
                    'bgcolor': _safe_hex_color(raw_cell.get('bgcolor')),
                    'textcolor': _safe_hex_color(raw_cell.get('textcolor')),
                })
            rows.append(row)
    else:
        _, header, data_rows, _ = _table_to_latex(ft.get('tbl_data', ''))
        legacy_rows = [header] + data_rows if header else data_rows
        rows = [[{'text': cell, 'colspan': 1, 'rowspan': 1,
                  'bold': False, 'italic': False, 'underline': False,
                  'align': 'left', 'bgcolor': '', 'textcolor': '',
                  '_escaped': True} for cell in row] for row in legacy_rows]

    if not rows:
        rows = [
            [{'text': 'Başlık 1', 'bold': True}, {'text': 'Başlık 2', 'bold': True}],
            [{'text': 'Veri'}, {'text': 'Veri'}],
        ]

    layout, ncols = _layout_table_rows(rows)
    raw_widths = raw_model.get('column_widths', []) if isinstance(raw_model, dict) else []
    widths = []
    if isinstance(raw_widths, list) and len(raw_widths) == ncols:
        try:
            widths = [max(0.01, float(width)) for width in raw_widths]
            if not all(math.isfinite(width) for width in widths):
                widths = []
        except (TypeError, ValueError):
            widths = []
    if not widths:
        widths = [1 / ncols] * ncols
    else:
        width_sum = sum(widths)
        widths = [width / width_sum for width in widths]

    header_rows = 1
    if isinstance(raw_model, dict):
        try:
            header_rows = max(0, min(int(raw_model.get('header_rows', 0)), len(rows)))
        except (TypeError, ValueError):
            header_rows = 0

    align_votes = [{'left': 0, 'center': 0, 'right': 0} for _ in range(ncols)]
    for entries in layout:
        for entry in entries:
            align = entry['cell'].get('align', 'left')
            for col in range(entry['col'], min(ncols, entry['col'] + entry['colspan'])):
                align_votes[col][align] += 1
    alignments = [max(votes, key=votes.get) for votes in align_votes]

    return {
        'rows': rows, 'layout': layout, 'ncols': ncols,
        'widths': widths, 'header_rows': header_rows,
        'alignments': alignments,
        'grid_borders': bool(raw_model.get('grid_borders')) if isinstance(raw_model, dict) else False,
    }


def _alignment_column_prefix(align: str) -> str:
    return {
        'center': r'>{\centering\arraybackslash}',
        'right': r'>{\raggedleft\arraybackslash}',
        'left': r'>{\raggedright\arraybackslash}',
    }[align]


def _format_table_cell(cell: dict, force_bold: bool = False) -> str:
    text = str(cell.get('text', ''))
    raw_lines = text.splitlines()
    while raw_lines and not raw_lines[0].strip():
        raw_lines.pop(0)
    while raw_lines and not raw_lines[-1].strip():
        raw_lines.pop()
    raw_lines = raw_lines or ['']
    if cell.get('_escaped'):
        lines = raw_lines
    else:
        lines = [escape(line) for line in raw_lines]
    # \makecell builds each explicit Word line as an unbreakable inner table.
    # Long list items then ignore the p-column width and can overlap adjacent
    # cells by several pages. \newline preserves the source line breaks while
    # still allowing every line to wrap naturally inside its column.
    content = r'\newline '.join(lines)
    if cell.get('italic'):
        content = r'\textit{' + content + '}'
    if cell.get('underline'):
        content = r'\uline{' + content + '}'
    if force_bold or cell.get('bold'):
        content = r'\textbf{' + content + '}'
    textcolor = _safe_hex_color(cell.get('textcolor'))
    if textcolor:
        content = r'\textcolor[HTML]{' + textcolor + '}{' + content + '}'
    bgcolor = _safe_hex_color(cell.get('bgcolor'))
    if bgcolor:
        content = r'\cellcolor[HTML]{' + bgcolor + '}' + content
    return content


def _rich_table_components(ft: dict) -> tuple[str, list[str], int, int, bool]:
    """Return column spec and LaTeX rows for a normalized rich table."""
    model = _normalize_table_model(ft)
    ncols = model['ncols']
    scaled_widths = model['widths']
    # Subtract padding and rules exactly. Percentage guesses overflow on wide
    # tables and make merged cells narrower than the columns they replace.
    padding = 6 * ncols + 0.2  # include outer cell padding and a rounding guard
    rules = (ncols + 1) * 0.4 if model['grid_borders'] else 0
    def cell_width(fraction, span=1):
        recovered = (6 + (0.4 if model['grid_borders'] else 0)) * (span - 1)
        return rf'\dimexpr {fraction:.6f}\JGTTRtablewidth-{fraction * (padding + rules):.4f}pt+{recovered:.4f}pt\relax'
    column_parts = [
        _alignment_column_prefix(align) + 'p{' + cell_width(width) + '}'
        for align, width in zip(model['alignments'], scaled_widths)
    ]
    col_spec = (
        '|' + '|'.join(column_parts) + '|'
        if model['grid_borders'] else ''.join(column_parts)
    )

    # longtable can break between rows, but not inside one enormous Word cell.
    # Split only oversized body rows into continuation rows, preserving every
    # character and leaving the companion cells empty when their text ends.
    expanded_layout = []
    for row_index, entries in enumerate(model['layout']):
        chunks_by_col = {}
        for entry in entries:
            text = str(entry['cell'].get('text', ''))
            fraction = sum(model['widths'][entry['col']:entry['col'] + entry['colspan']])
            budget = max(120, int(105 * fraction) * 24)
            chunks = []
            while len(text) > budget and row_index >= model['header_rows']:
                boundary = text.rfind(' ', 0, budget)
                if boundary <= 0:
                    break
                chunks.append(text[:boundary + 1])
                text = text[boundary + 1:]
            chunks.append(text)
            chunks_by_col[entry['col']] = chunks
        for index in range(max((len(chunks) for chunks in chunks_by_col.values()), default=1)):
            expanded_layout.append((row_index, [
                {**entry, 'cell': {**entry['cell'], 'text':
                    chunks_by_col[entry['col']][index] if index < len(chunks_by_col[entry['col']]) else ''}}
                for entry in entries
            ]))

    latex_rows = []
    for row_index, entries in expanded_layout:
        by_column = {entry['col']: entry for entry in entries}
        tokens = []
        col = 0
        while col < ncols:
            entry = by_column.get(col)
            if entry is None:
                tokens.append('')
                col += 1
                continue

            cell = entry['cell']
            colspan = entry['colspan']
            content = _format_table_cell(cell, row_index < model['header_rows'])
            # Do not use \multirow here. It does not increase the physical row
            # height, so long Word cells can overlap following rows. The grid
            # layout already leaves the covered cells empty; keeping the text
            # in the first row preserves the merge visually without overlap.

            cell_align = _cell_alignment(cell.get('align'))
            column_align = model['alignments'][col]
            if colspan > 1 or cell_align != column_align:
                span_width = sum(scaled_widths[col:min(ncols, col + colspan)])
                span_spec = _alignment_column_prefix(cell_align) + 'p{' + cell_width(span_width, colspan) + '}'
                if model['grid_borders']:
                    span_spec = ('|' if col == 0 else '') + span_spec + '|'
                content = r'\multicolumn{' + str(colspan) + '}{' + span_spec + '}{' + content + '}'

            tokens.append(content)
            col += colspan

        row_suffix = r' \\ \hline' if model['grid_borders'] else r' \\'
        latex_rows.append(' & '.join(tokens) + row_suffix)

    return col_spec, latex_rows, ncols, model['header_rows'], model['grid_borders']


def _build_figtable_latex(ft: dict, file_ext_map: dict, english_only: bool = False) -> str:
    """Return LaTeX for one figure or table item."""
    num     = ft.get('number', '1')
    tr_cap  = escape(ft.get('tr_cap', ''))
    en_cap  = escape(ft.get('en_cap', ''))
    caption = (en_cap or tr_cap) if english_only else ' / '.join(part for part in (tr_cap, en_cap) if part)
    label   = ('fig' if ft.get('type') == 'figure' else 'tbl') + re.sub(r'[^A-Za-z0-9_-]', '_', str(num))

    if ft.get('type') == 'figure':
        fkey = ft.get('file_key', '')
        stem = file_ext_map.get(fkey, 'figure_' + str(num))
        try:
            width_percent = int(float(ft.get('fig_width', 90) or 90))
        except (TypeError, ValueError):
            width_percent = 90
        width_percent = max(50, min(100, width_percent))
        width_ratio = width_percent / 100
        return (
            (r'\begin{figure}[H]' if ft.get('float_placement') == 'exact' else r'\begin{figure}[htbp]') + '\n'
            r'  \centering' + '\n'
            rf'  \includegraphics[width={width_ratio:.2f}\linewidth,height=0.56\textheight,keepaspectratio]{{' + stem + '}\n'
            r'  \caption{' + caption + '}\n'
            r'  \label{' + label + '}\n'
            r'\end{figure}'
        )
    else:
        # ── Table ──
        normalized = _normalize_table_model(ft)
        split_table = ft.get('split_table', False) or _table_requires_page_split({
            'rows': normalized['rows'], 'column_widths': normalized['widths'],
        })
        tbl_fontsize = str(ft.get('tbl_fontsize', '') or '').strip()

        # Font size command
        if tbl_fontsize:
            try:
                fs      = float(tbl_fontsize)
                fs = max(7.0, min(12.0, fs)) if math.isfinite(fs) else 9.0
                leading = round(fs * 1.2, 1)
                font_open  = r'{\fontsize{' + str(fs) + r'}{' + str(leading) + r'}\selectfont' + '\n'
                font_close = '}'
            except ValueError:
                font_open = font_close = ''
        else:
            font_open, font_close = '{\\fontsize{9}{10.8}\\selectfont\n', '}'

        col_spec, latex_rows, ncols, header_count, grid_borders = _rich_table_components(ft)
        header_rows = latex_rows[:header_count]
        data_rows = latex_rows[header_count:]
        header_block = '\n'.join(header_rows)
        data_block = '\n'.join(data_rows)
        top_rule = r'  \hline' if grid_borders else r'  \toprule'
        midrule = '' if grid_borders else (r'  \midrule' + '\n' if header_rows else '')
        bottom_rule = '' if grid_borders else r'  \bottomrule' + '\n'

        if split_table:
            # ── longtable (splits across pages) ──
            cont_msg = r'\multicolumn{' + str(ncols) + r'}{l}{\small\textit{devamı / continued\ldots}} \\'
            cont_next = r'\multicolumn{' + str(ncols) + r'}{r}{\small\textit{devam ediyor / continued on next page}} \\'
            parts = [
                r'\begingroup' + '\n',
                font_open,
                r'\setlength{\JGTTRtablewidth}{\linewidth}' + '\n',
                r'\setlength{\tabcolsep}{3pt}' + '\n',
                r'\renewcommand{\arraystretch}{1.12}' + '\n',
                r'\begin{longtable}{' + col_spec + r'}' + '\n',
                r'  \caption{' + caption + r'} \label{' + label + r'} \\' + '\n',
                top_rule + '\n',
                ('  ' + header_block.replace('\n', '\n  ') + '\n') if header_block else '',
                midrule,
                r'  \endfirsthead' + '\n',
                r'  ' + cont_msg + '\n',
                top_rule + '\n',
                ('  ' + header_block.replace('\n', '\n  ') + '\n') if header_block else '',
                midrule,
                r'  \endhead' + '\n',
                (r'  \hline' if grid_borders else r'  \midrule') + '\n',
                r'  ' + cont_next + '\n',
                r'  \endfoot' + '\n',
                bottom_rule,
                r'  \endlastfoot' + '\n',
                ('  ' + data_block.replace('\n', '\n  ') + '\n') if data_block else '',
                r'\end{longtable}' + '\n',
                font_close,
                '\n' if font_close else '',
                r'\endgroup' + '\n',
            ]
            return ''.join(parts)
        else:
            # ── regular table[htbp] ──
            tabular_body = ''.join([
                r'\setlength{\JGTTRtablewidth}{\linewidth}' + '\n',
                r'\setlength{\tabcolsep}{3pt}' + '\n',
                r'\renewcommand{\arraystretch}{1.12}' + '\n',
                r'\begin{adjustbox}{max width=\linewidth,center}' + '\n',
                r'\begin{tabular}{' + col_spec + r'}' + '\n',
                top_rule + '\n',
                ('  ' + header_block.replace('\n', '\n  ') + '\n') if header_block else '',
                midrule,
                ('  ' + data_block.replace('\n', '\n  ') + '\n') if data_block else '',
                bottom_rule,
                r'\end{tabular}' + '\n',
                r'\end{adjustbox}',
            ])
            return (
                (r'\begin{table}[H]' if ft.get('float_placement') == 'exact' else r'\begin{table}[htbp]') + '\n'
                r'  \centering' + '\n'
                r'  \caption{' + caption + '}\n'
                r'  \label{' + label + '}\n'
                + r'  \begingroup' + '\n'
                + (font_open + '  ' if font_open else '  ')
                + tabular_body.replace('\n', '\n  ') + '\n'
                + (font_close + '\n' if font_close else '')
                + r'  \endgroup' + '\n'
                + r'\end{table}'
            )


def _cover_profile(data: dict, settings: dict) -> dict:
    """Choose readable density before the measured one-page fit is applied."""
    cov, abstract = data.get('cover', {}), data.get('abstract', {})
    requested = cov.get('first_page_fit') or settings['first_page_fit']
    if requested not in {'auto', 'compact', 'dense'}:
        requested = settings['first_page_fit']
    profiles = {
        'auto': {'title': ('13', '15.5'), 'subtitle': ('11.5', '14'),
                 'abstract': ('9', '10'), 'info': ('7.5', '9'), 'authors': ('10', '12'),
                 'footer': ('7', '8.5'), 'gap': '1.5mm'},
        'compact': {'title': ('12.3', '14.3'), 'subtitle': ('11', '13'),
                    'abstract': ('8.6', '9.5'), 'info': ('7.2', '8.5'), 'authors': ('9.5', '11'),
                    'footer': ('6.6', '7.9'), 'gap': '1mm'},
        'dense': {'title': ('11.7', '13.5'), 'subtitle': ('10.5', '12.2'),
                  'abstract': ('8.1', '9'), 'info': ('6.9', '8.1'), 'authors': ('9', '10.5'),
                  'footer': ('6.2', '7.3'), 'gap': '0.6mm'},
    }
    mode = requested
    if mode == 'auto':
        load = sum(len(str(v or '')) for v in [
            cov.get('tr_title'), cov.get('en_title'), cov.get('ethics'), cov.get('title_note'),
            settings.get('footer_text'), *abstract.values(),
        ]) + sum(len(str(a.get(k, ''))) for a in data.get('authors', []) for k in ('name', 'affiliation', 'email'))
        if load > 3800 or len(data.get('authors', [])) > 6:
            mode = 'dense'
        elif load > 2400 or len(data.get('authors', [])) > 4:
            mode = 'compact'
    return {**profiles[mode], 'mode': mode}


def _optional_graphic(stem: str, options: str) -> str:
    """Controlled stems only; a journal can produce a PDF before uploading a logo."""
    result = ''
    for extension in reversed(('png', 'jpg', 'jpeg', 'pdf')):
        filename = stem + '.' + extension
        result = (r'\IfFileExists{' + filename + r'}{\includegraphics[' + options + ']{' + filename + '}}{' + result + '}')
    return result


def _first_page_layout(data: dict, js: dict, english_only: bool, has_tr: bool,
                       has_en: bool, has_authors: bool) -> str:
    """Render four real cover structures with a separately measured footer."""
    cov = data.get('cover', {})
    profile = _cover_profile(data, js)
    layout, footer_layout = js['template_id'], js['footer_layout']
    jname_tr, jname_en = _journal_names_for_output(js, english_only)
    primary_name = jname_en if english_only else (jname_tr or jname_en)
    secondary = jname_en if not english_only and jname_en != primary_name else ''
    names = r'{\bfseries ' + escape(primary_name) + r'\par}'
    if secondary:
        names += r'{\itshape ' + escape(secondary) + r'\par}'
    identifiers = []
    for label, key in [('ISSN', 'issn_print'), ('e-ISSN', 'issn_online')]:
        if js[key]:
            identifiers.append(label + ': ' + escape(js[key]))
    details = (r'\quad '.join(identifiers) + r'\par ') if identifiers else ''
    if js['journal_url']:
        details += _escape_with_breakable_urls(js['journal_url']) + r'\par '
    has_doi = bool(str(cov.get('doi', '') or '').strip())
    doi = r'\textbf{DOI:} \JGTTRdoilink\par ' if has_doi else ''
    if js['doi_position'] == 'top':
        details += doi
    logo = _optional_graphic(js['logo_stem'], f'height={js["logo_height_cm"]}cm,width=0.25\\textwidth,keepaspectratio')
    if not js.get('show_logo', True):
        logo = ''
    identity = r'{\fontsize{10}{12}\selectfont ' + names + r'}{\fontsize{7.5}{9}\selectfont ' + details + '}'
    if layout == 'classic':
        header = (r'\noindent\begin{minipage}[c]{0.30\textwidth}' + logo + r'\end{minipage}\hfill'
                  r'\begin{minipage}[c]{0.67\textwidth}\raggedleft ' + identity + r'\end{minipage}\par'
                  r'\noindent\textcolor{JGTTRbrown}{\rule{\textwidth}{0.7pt}}\par')
    elif layout == 'contemporary':
        header = (r'{\setlength{\fboxsep}{8pt}\noindent\colorbox{JGTTRbrown}{'
                  r'\begin{minipage}[c]{\dimexpr0.72\textwidth-16pt\relax}\color{white}'
                  r'{\fontsize{12}{14}\selectfont ' + names + r'}\end{minipage}}}\hfill'
                  r'\begin{minipage}[c]{0.25\textwidth}\raggedleft ' + logo + r'\end{minipage}\par'
                  r'\vspace{2pt}{\fontsize{7.5}{9}\selectfont ' + details + r'}')
    elif layout == 'centered':
        header = (r'{\centering ' + logo + r'\par\vspace{2pt}' + identity + r'\par}'
                  r'\noindent\textcolor{JGTTRbrown}{\rule{\textwidth}{0.4pt}}\par')
    else:
        header = (r'\noindent\begin{minipage}[c]{0.78\textwidth}' + identity + r'\end{minipage}\hfill'
                  r'\begin{minipage}[c]{0.19\textwidth}\raggedleft ' + logo + r'\end{minipage}\par'
                  r'\vspace{3pt}\noindent\rule{\textwidth}{0.2pt}\par')

    meta = _build_meta_strip(english_only)
    if layout in {'classic', 'contemporary'}:
        meta = (r'{\setlength{\fboxsep}{3pt}\noindent\colorbox{JGTTRgray!35}{'
                r'\begin{minipage}{\dimexpr\textwidth-6pt\relax}' + meta + r'\end{minipage}}}\par')
    else:
        meta = r'{\noindent ' + (r'\centering ' if layout == 'centered' else '') + meta + r'\par}'
    title_style = r'\centering ' if layout == 'centered' else ''
    if layout == 'contemporary':
        title_style += r'\color{JGTTRbrown}'
    title_parts = []
    for macro, key, italic in (
        [('JGTTRenglishtitle', 'title', '')] if english_only else
        [('JGTTRturkishtitle', 'title', ''), ('JGTTRenglishtitle', 'subtitle', r'\itshape')]
    ):
        size, leading = profile[key]
        title_parts.append(r'{\noindent ' + title_style + rf'\fontsize{{{size}}}{{{leading}}}\selectfont\bfseries' + italic + '\\' + macro + r'\par}')
    titles = ('\n' + r'\vspace{0.8mm}' + '\n').join(title_parts)
    author_size, author_leading = profile['authors']
    authors = (r'{\noindent ' + (r'\centering ' if layout == 'centered' else '')
               + rf'\fontsize{{{author_size}}}{{{author_leading}}}\selectfont #1\par}}') if has_authors else ''
    editor = str(cov.get('editor', '') or '').strip()
    if layout == 'classic':
        abstract = _build_abstract_block(english_only, has_tr, has_en, editor)
        abs_size, abs_leading = profile['abstract']
        info_size, info_leading = profile['info']
        abstract = abstract.replace(r'\fontsize{8.5}{10.5}', rf'\fontsize{{{abs_size}}}{{{abs_leading}}}')
        abstract = abstract.replace(r'\selectfont\JGTTR', r'\selectfont\itshape\JGTTR')
        abstract = abstract.replace(r'\fontsize{7.5}{9}', rf'\fontsize{{{info_size}}}{{{info_leading}}}')
    else:
        # Flat metadata and full-width or side-by-side abstract columns.
        date_labels = [('Received', 'received'), ('Accepted', 'accepted'), ('Published', 'published')]
        if not english_only:
            date_labels = [('Başvuru / Received', 'received'), ('Kabul / Accepted', 'accepted'), ('Yayın / Published', 'published')]
        dates = [escape(label) + ': ' + '\\JGTTR' + key for label, key in date_labels if cov.get(key)]
        if editor:
            dates.append(('Editor: ' if english_only else 'Editör / Editor: ') + escape(editor))
        abstract = (r'{\fontsize{7.5}{9}\selectfont ' + r'\quad '.join(dates) + r'\par}\vspace{4pt}') if dates else ''
        languages = ([('Özet', 'turkish', 'Anahtar kelimeler')] if has_tr and not english_only else [])
        languages += [('Abstract', 'english', 'Keywords')] if has_en else []
        columns = layout == 'contemporary' and len(languages) == 2
        rendered = []
        for label, language, keyword_label in languages:
            size, leading = profile['abstract']
            block = (r'{\bfseries\color{JGTTRbrown}' + label + r'\par}\vspace{2pt}'
                     + rf'{{\fontsize{{{size}}}{{{leading}}}\selectfont\itshape\JGTTR' + language + r'abstract\par}'
                     + r'\vspace{3pt}{\fontsize{7.5}{9}\selectfont\textbf{' + keyword_label + ': }'
                     + '\\JGTTR' + language + r'keywords\par}')
            if columns:
                block = r'\begin{minipage}[t]{0.48\textwidth}\vspace{0pt}' + block + r'\end{minipage}'
            rendered.append(block)
        abstract += (r'\hfill' if columns else r'\par\vspace{5pt}').join(rendered)

    footer_parts = []
    if has_authors:
        footer_parts.append(r'\JGTTRaffiliations\par')
        footer_parts.append(r'\textit{' + _build_corresponding_label(english_only, _latex_marker(js['corresponding_marker']))
                            + r': \JGTTRcorrespondinginfo}\par')
    if footer_layout != 'minimal':
        footer_parts.append(r'\textbf{' + ('Suggested Citation: ' if english_only else 'Önerilen Atıf / Suggested Citation: ')
                            + r'}\JGTTRapacitation\par')
    if str(cov.get('ethics', '') or '').strip():
        footer_parts.append(r'\textbf{' + ('Ethics Statement: ' if english_only else 'Etik Beyan / Ethics Statement: ')
                            + r'}\JGTTRethicsstatement\par')
    if str(cov.get('title_note', '') or '').strip():
        footer_parts.append(r'\textit{' + escape(cov['title_note']) + r'}\par')
    if js['footer_text']:
        footer_parts.append(_escape_with_breakable_urls(js['footer_text']) + r'\par')
    if js['doi_position'] == 'bottom' and doi:
        footer_parts.append(doi)
    license_logo = _optional_graphic(js['cc_logo_stem'], r'height=0.55cm,width=0.35\textwidth,keepaspectratio')
    if js.get('show_cc_logo', True):
        footer_parts.append(license_logo)
    footer = '\n'.join(footer_parts)
    footer_size, footer_leading = profile['footer']
    # A long ethics statement should use spare cover space before shrinking.
    # Short abstracts leave more room for affiliations and editorial notes.
    body_chars = sum(len(str(v or '')) for v in data.get('abstract', {}).values())
    body_chars += len(str(cov.get('tr_title', ''))) + len(str(cov.get('en_title', '')))
    footer_max_height = '0.60' if body_chars < 1400 else '0.40'
    footer_rule = (r'\noindent\textcolor{JGTTRbrown}{\rule{\textwidth}{0.5pt}}\par'
                   if footer_layout == 'full' else r'\noindent\rule{\textwidth}{0.2pt}\par') if footer_layout != 'minimal' else ''
    gap = profile['gap']
    return ('% Template: ' + layout + '; footer: ' + footer_layout + '\n'
            '% First-page density profile: ' + profile['mode'] + '\n' + r'''
\newsavebox{\JGTTRfooterbox}
\newcommand{\JGTTRfirstpagefooter}{%
  \begin{adjustbox}{max width=\textwidth,max totalheight=__FOOTER_MAX_HEIGHT__\textheight,center}%
  \begin{minipage}{\textwidth}%
  \sloppy\emergencystretch=3em\setlength{\parindent}{0pt}%
''' + (r'\setlength{\parskip}{0pt}' if footer_layout != 'full' else r'\setlength{\parskip}{1pt}')
            + rf'\fontsize{{{footer_size}}}{{{footer_leading}}}\selectfont' + '\n'
            + footer_rule + '\n' + footer + '\n' + r'''
  \end{minipage}%
  \end{adjustbox}%
}
\newcommand{\JGTTRfirstpage}[1]{%
  \newgeometry{includehead=false,top=1.2cm,bottom=1.5cm,left=1.5cm,right=1.5cm,headheight=0pt,headsep=0pt,footskip=0.8cm}%
  \thispagestyle{firstpage}%
  \begin{lrbox}{\JGTTRfooterbox}%
    \begin{minipage}{\textwidth}\JGTTRfirstpagefooter\end{minipage}%
  \end{lrbox}%
  \noindent\begin{adjustbox}{max width=\textwidth,max totalheight={\dimexpr\textheight-\ht\JGTTRfooterbox-\dp\JGTTRfooterbox-2mm\relax},center}%
  \begin{minipage}{\textwidth}%
''' + header + '\n' + meta + '\n' + rf'\vspace{{{gap}}}'
            + r'{\fontsize{9}{11}\selectfont\itshape\JGTTRarticletype\par}' + rf'\vspace{{{gap}}}'
            + titles + rf'\vspace{{{gap}}}' + authors + rf'\vspace{{{gap}}}' + abstract + '\n' + r'''
  \end{minipage}%
  \end{adjustbox}\par%
  \vspace*{\fill}%
  \noindent\usebox{\JGTTRfooterbox}%
  \restoregeometry%
}
''').replace('__FOOTER_MAX_HEIGHT__', footer_max_height)


def generate_latex_from_form(data: dict, figure_file_bytes: dict,
                             journal_settings: dict = None) -> str:
    """
    Generate complete LaTeX from structured form data.
    data keys: cover, authors, abstract, sections, figtables, extra, references
    figure_file_bytes: {file_key: (filename_in_zip, bytes)} for figure files
    journal_settings: optional journal branding/typography overrides
    """
    # ── Validated journal preferences ──
    js          = normalize_settings(journal_settings)
    english_only      = bool(js.get('english_only', False))
    jname_tr, jname_en = _journal_names_for_output(js, english_only)
    font_name   = js.get('font_family', 'texgyrepagella')
    body_size   = js.get('body_size',   '10')
    accent_hex  = js.get('accent_color', '#833C0B').lstrip('#')
    corr_marker = js['corresponding_marker']

    # Explicit TeX-distributed file names work on Overleaf and local engines
    # without relying on the operating system's font cache.
    font_files = {
        'texgyrepagella': ('texgyrepagella', 'texgyrepagella-math.otf'),
        'texgyretermes': ('texgyretermes', 'texgyretermes-math.otf'),
        'texgyrebonum': ('texgyrebonum', 'texgyrebonum-math.otf'),
        'texgyreheros': ('texgyreheros', 'latinmodern-math.otf'),
    }
    if font_name in font_files:
        family, math_font = font_files[font_name]
        font_setup = (r'\setmainfont{' + family + r'-regular.otf}['
                      'BoldFont=' + family + '-bold.otf,'
                      'ItalicFont=' + family + '-italic.otf,'
                      'BoldItalicFont=' + family + '-bolditalic.otf]')
    elif font_name == 'carlito':
        font_setup = (r'\setmainfont{Carlito-Regular.ttf}['
                      'BoldFont=Carlito-Bold.ttf,ItalicFont=Carlito-Italic.ttf,'
                      'BoldItalicFont=Carlito-BoldItalic.ttf]')
        math_font = 'latinmodern-math.otf'
    else:
        font_setup = (r'\setmainfont{lmroman10-regular.otf}['
                      'BoldFont=lmroman10-bold.otf,ItalicFont=lmroman10-italic.otf,'
                      'BoldItalicFont=lmroman10-bolditalic.otf]')
        math_font = 'latinmodern-math.otf'
    font_setup += '\n' + r'\setmathfont{' + math_font + '}'

    cov      = data.get('cover', {})
    authors  = [a for a in data.get('authors', []) if (a.get('name') or '').strip()]
    abstr    = data.get('abstract', {})
    sections = data.get('sections', [])
    fts      = data.get('figtables', [])
    extra    = data.get('extra', {})
    refs_raw = data.get('references', '')

    # ── Cover fields ──
    tr_title_raw = (cov.get('tr_title', '') or '').strip()
    en_title_raw = (cov.get('en_title', '') or '').strip()
    if english_only:
        title_for_english = en_title_raw or tr_title_raw or 'Article Title in English'
        tr_title = escape(tr_title_raw or title_for_english)
        en_title = escape(title_for_english)
    else:
        tr_title = escape(tr_title_raw or 'Makalenin Türkçe Adı')
        en_title = escape(en_title_raw or 'Article Title in English')
    year       = escape(cov.get('year',       '2026'))
    volume     = escape(cov.get('volume',     'x'))
    issue      = escape(cov.get('issue',      'x'))
    start_page = escape(cov.get('start_page', 'xxx'))
    end_page   = escape(cov.get('end_page',   'xxx'))
    doi        = escape(str(cov.get('doi', '') or '').removeprefix('https://doi.org/').removeprefix('doi:').strip())
    art_type_raw = cov.get('article_type', 'Araştırma Makalesi -- Research Article')
    art_type   = escape(_english_label(art_type_raw) if english_only else art_type_raw)
    received   = escape(cov.get('received',  'xx.xx.xxxx'))
    accepted   = escape(cov.get('accepted',  'xx.xx.xxxx'))
    published  = escape(cov.get('published', 'xx.xx.xxxx'))
    ethics_raw = cov.get('ethics', '').strip()
    ethics = escape(ethics_raw)

    # ── Author short / head title ──
    author_short = cov.get('author_short', '').strip()
    if not author_short and authors:
        names = [a['name'].split()[-1] for a in authors if a.get('name')]
        if len(names) == 1:
            author_short = names[0]
        elif len(names) == 2:
            author_short = names[0] + ' & ' + names[1]
        elif names:
            author_short = names[0] + r' et al.'
    if not author_short:
        author_short = ''
    else:
        author_short = escape(author_short)

    head_title = escape(_title_without_footnote_marker(en_title_raw or tr_title_raw) if english_only else _title_without_footnote_marker(tr_title_raw or en_title_raw))

    # ── Abstract / keywords (boş olabilirler) ──
    tr_abs_raw = (abstr.get('tr_abs', '') or '').strip()
    en_abs_raw = (abstr.get('en_abs', '') or '').strip()
    tr_kw_raw  = (abstr.get('tr_kw',  '') or '').strip()
    en_kw_raw  = (abstr.get('en_kw',  '') or '').strip()
    tr_abs = escape(tr_abs_raw)
    en_abs = escape(en_abs_raw)
    tr_kw  = escape(tr_kw_raw)
    en_kw  = escape(en_kw_raw)
    has_tr_abs = bool(tr_abs_raw) and not english_only
    has_en_abs = bool(en_abs_raw)

    # ── Author blocks ──
    author_block = _format_author_block(authors, corr_marker) if authors else ''
    affiliations = _format_affiliations(authors, english_only) if authors else ''
    corresponding = _format_corresponding(authors, english_only) if authors else ''

    # ── APA citation ──
    citation_title = en_title if english_only else tr_title
    citation_journal = jname_en or jname_tr
    apa_citation = (
        author_short + r'\ (' + year + r'). ' + citation_title +
        r'. \textit{' + escape(citation_journal) + r'}, ' +
        r'\textit{' + volume + r'}(' + issue + r'), ' +
        start_page + r'--' + end_page + r'.'
    )

    # ── Figure file → zip name mapping ──
    # file_ext_map: {file_key: 'fig_N'} (no extension; XeLaTeX resolves)
    file_ext_map = {}
    for fkey, (zipname, _) in figure_file_bytes.items():
        # zipname like 'fig_3.png' → stem 'fig_3'
        stem = zipname.rsplit('.', 1)[0] if '.' in zipname else zipname
        file_ext_map[fkey] = stem

    # ── Body sections + paragraph-level figure/table placement ──
    body_lines = []
    placed_ft_ids = set()   # track which fts have already been placed

    for sec in sections:
        raw_name = (sec.get('name', 'Bölüm') or '').strip()
        detected = _numbered_section_title(raw_name)
        if detected:
            raw_name = detected[0]
        name    = _english_label(raw_name) if english_only else raw_name
        if not name:
            name = 'Section' if english_only else 'Bölüm'
        level   = str(sec.get('level', '1'))
        content = sec.get('content', '').strip()
        cmd     = SECTION_CMD_MAP.get(level, r'\section')
        starred = any(k in (raw_name + ' ' + name).lower() for k in STARRED_NAMES)
        star    = '*' if starred else ''
        body_lines.append(cmd + star + '{' + escape(name) + '}')
        body_lines.append('')

        # FTs assigned to this section
        sec_fts = [
            (i, ft) for i, ft in enumerate(fts)
            if (str(ft.get('section_id')) == str(sec.get('id'))
                if ft.get('section_id') is not None and sec.get('id') is not None
                else ft.get('section', '').strip() == str(sec.get('name', '')).strip()) and i not in placed_ft_ids
        ]

        for i, ft in sec_fts:
            if ft.get('placement') == 'section_start':
                body_lines.extend([_build_figtable_latex(ft, file_ext_map, english_only), ''])
                placed_ft_ids.add(i)

        if content:
            # Split content into paragraphs (blank-line separated or single newlines)
            raw_paras = [p.strip() for p in re.split(r'\n\s*\n', content)]
            raw_paras = [p for p in raw_paras if p]
            if not raw_paras:
                raw_paras = [content]

            for para in raw_paras:
                body_lines.append(_escape_with_breakable_urls(para))
                body_lines.append('')

                # Check if any ft's anchor text is found in this paragraph
                for i, ft in sec_fts:
                    if i in placed_ft_ids:
                        continue
                    anchor = ft.get('after_para', '').strip()
                    if anchor and anchor.lower() in para.lower():
                        body_lines.append(_build_figtable_latex(ft, file_ext_map, english_only))
                        body_lines.append('')
                        placed_ft_ids.add(i)

            # FTs for this section with anchor NOT found → append at section end
            for i, ft in sec_fts:
                if i not in placed_ft_ids:
                    body_lines.append(_build_figtable_latex(ft, file_ext_map, english_only))
                    body_lines.append('')
                    placed_ft_ids.add(i)
        else:
            # No content — place all section FTs here
            for i, ft in sec_fts:
                if i not in placed_ft_ids:
                    body_lines.append(_build_figtable_latex(ft, file_ext_map, english_only))
                    body_lines.append('')
                    placed_ft_ids.add(i)

    if not body_lines:
        body_lines = [
            r'\section{Introduction}' if english_only else r'\section{Giriş / Introduction}',
            '',
            r'% Article body goes here' if english_only else r'% Makale metni buraya gelecek / Article body goes here',
            '',
        ]

    # ── Figures/tables with no section assigned (end of body) ──
    orphan_fts = [
        (i, ft) for i, ft in enumerate(fts)
        if i not in placed_ft_ids
    ]
    if orphan_fts:
        body_lines.append(r'% Figures and Tables' if english_only else r'% ── Şekil ve Tablolar / Figures and Tables ──')
        body_lines.append(r'\clearpage')
        for i, ft in orphan_fts:
            body_lines.append(_build_figtable_latex(ft, file_ext_map, english_only))
            body_lines.append('')
            placed_ft_ids.add(i)

    # ── Extra sections (başlıklar dil moduna göre) ──
    ack_heading      = 'Acknowledgements' if english_only else r'Teşekkür / Acknowledgements'
    contrib_heading  = 'Author Contributions' if english_only else r'Araştırmacıların Katkı Oranı / Author Contributions'
    conflict_heading = 'Conflict of Interest' if english_only else r'Çıkar Çatışması / Conflict of Interest'

    ack = extra.get('ack', '').strip()
    if ack:
        body_lines.append(r'\section*{' + ack_heading + r'}')
        body_lines.append(escape(ack))
        body_lines.append('')

    for field, heading in (('contrib', contrib_heading), ('conflict', conflict_heading)):
        value = str(extra.get(field, '') or '').strip()
        if value:
            body_lines.extend([r'\section*{' + heading + '}', escape(value), ''])

    # ── References — alphabetically sorted, hanging indent, no numbers ──
    refs_lines = sorted(
        [l.strip() for l in refs_raw.splitlines() if l.strip()],
        key=turkish_sort_key
    )
    refs_heading = 'References' if english_only else r'Kaynakça / References'
    _ref_env_open = (
        r'\section*{' + refs_heading + r'}' + '\n'
        r'\begin{list}{}{%' + '\n'
        r'  \setlength{\leftmargin}{1.5em}%' + '\n'
        r'  \setlength{\itemindent}{-1.5em}%' + '\n'
        r'  \setlength{\topsep}{2pt}%' + '\n'
        r'  \setlength{\itemsep}{3pt}%' + '\n'
        r'  \setlength{\parsep}{0pt}%' + '\n'
        r'}' + '\n'
    )
    if refs_lines:
        items = '\n'.join(r'\item ' + _escape_with_breakable_urls(r) for r in refs_lines)
        refs_tex = _ref_env_open + items + '\n' + r'\end{list}'
    else:
        refs_tex = ''

    body_text = '\n'.join(body_lines)
    doi_line  = doi if doi else ''

    # ── Full LaTeX document ──
    tex = r"""% ============================================================
%  """ + escape(jname_en) + r"""
%  Bu dosya Journal LaTeX Formatter tarafından oluşturulmuştur.
%  Overleaf: New Project → Upload Project → bu ZIP'i seçin.
%  Derleyici: XeLaTeX
% ============================================================

\documentclass[""" + body_size + r"""pt,a4paper]{article}

\usepackage{fontspec}
\usepackage{unicode-math}
\usepackage{geometry}
\usepackage{fancyhdr}
\usepackage{microtype}
\usepackage[table]{xcolor}
\usepackage{titlesec}
\usepackage{array}
\usepackage{tabularx}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{makecell}
\usepackage{longtable}
\usepackage{graphicx}
\usepackage{adjustbox}
\usepackage[normalem]{ulem}
\newlength{\JGTTRtablewidth}
\usepackage{float}
\usepackage{caption}
\usepackage{amsmath}
\usepackage{hyperref}
\usepackage{url}
\usepackage{doi}
\usepackage[numbers,sort&compress]{natbib}
\usepackage{orcidlink}
\usepackage{marvosym}
\usepackage{footmisc}
\usepackage{enumitem}
\usepackage{etoolbox}
\usepackage{calc}
\usepackage{lastpage}
\usepackage{ifthen}

% ── Font ──
""" + font_setup + r"""

% ── Colours ──
\definecolor{JGTTRbrown}{HTML}{""" + accent_hex + r"""}
\definecolor{JGTTRblue}{HTML}{0070C0}
\definecolor{JGTTRgray}{HTML}{CFCDCD}
\definecolor{JGTTRdarkgray}{HTML}{3B3838}

% ── Hyperlinks ──
\hypersetup{colorlinks=true,urlcolor=JGTTRblue,linkcolor=black,citecolor=black,pdfencoding=auto,unicode=true}
% URL'leri bölme — sığmazsa bütün olarak alt satıra geç
\renewcommand{\UrlBreaks}{}
\renewcommand{\UrlBigBreaks}{}

% ── Geometry ──
\geometry{a4paper,top=1.5cm,bottom=1.5cm,left=1.5cm,right=1.5cm,headheight=1.2cm,headsep=0.4cm,footskip=0.8cm}

% ── Paragraph format ──
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\renewcommand{\baselinestretch}{1.0}

% ── Satır kırma / Line breaking ──
% Uzun kelimeler ve URL'lerin sayfa kenarına taşmasını önler
\setlength{\emergencystretch}{3em}
\tolerance=800
\hyphenpenalty=50
\exhyphenpenalty=50

% ── Section headings ──
\titleformat{\section}[block]{\fontsize{11}{13}\selectfont\bfseries\centering}{}{0em}{}
\titlespacing*{\section}{0pt}{9pt}{5pt}
\titleformat*{\section}{\fontsize{11}{13}\selectfont\bfseries\centering}
\titleformat{\subsection}[block]{\fontsize{11}{13}\selectfont\bfseries}{}{0em}{}
\titlespacing*{\subsection}{0pt}{7pt}{3pt}
\titleformat{\subsubsection}[block]{\fontsize{11}{13}\selectfont\bfseries\itshape}{}{0em}{}
\titlespacing*{\subsubsection}{0pt}{6pt}{3pt}

% ── Headers & footers ──
\pagestyle{fancy}
\fancyhf{}
\fancyhead[C]{%
  \fontsize{8.5}{10.5}\selectfont
  """ + author_short + r"""\ (""" + year + r""").
  """ + head_title + r""".
  \textit{""" + escape(citation_journal) + r"""},
  \textit{""" + volume + r"""}(""" + issue + r"""),
  """ + start_page + r"""--""" + end_page + r"""%
}
\fancyfoot[C]{\fontsize{9}{11}\selectfont\thepage}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\fancypagestyle{firstpage}{\fancyhf{}\renewcommand{\headrulewidth}{0pt}}

% ── Caption format ──
\captionsetup{font={small,bf},labelsep=period,justification=centering,skip=4pt}
\captionsetup[table]{position=top}

% ── Footnote format ──
\renewcommand{\footnoterule}{\kern-3pt\hrule width 2cm height 0.4pt\kern 2.6pt}
\setlength{\footnotesep}{4pt}

% ── List format ──
\setlist{leftmargin=1.2cm,itemsep=0pt,parsep=0pt,topsep=2pt,partopsep=0pt}

% ── Bibliography ──
\bibliographystyle{unsrtnat}
\setlength{\bibhang}{1.5em}
\setlength{\bibsep}{3pt}

% ── Article metadata ──
\newcommand{\JGTTRyear}{""" + year + r"""}
\newcommand{\JGTTRvolume}{""" + volume + r"""}
\newcommand{\JGTTRissue}{""" + issue + r"""}
\newcommand{\JGTTRstartpage}{""" + start_page + r"""}
\newcommand{\JGTTRendpage}{""" + end_page + r"""}
\newcommand{\JGTTRDOI}{""" + doi_line + r"""}
\newcommand{\JGTTRarticletype}{""" + art_type + r"""}
\newcommand{\JGTTRreceived}{""" + received + r"""}
\newcommand{\JGTTRaccepted}{""" + accepted + r"""}
\newcommand{\JGTTRpublished}{""" + published + r"""}
\newcommand{\JGTTRturkishtitle}{""" + tr_title + r"""}
\newcommand{\JGTTRturkishabstract}{""" + tr_abs + r"""}
\newcommand{\JGTTRturkishkeywords}{""" + tr_kw + r"""}
\newcommand{\JGTTRenglishtitle}{""" + en_title + r"""}
\newcommand{\JGTTRenglishabstract}{""" + en_abs + r"""}
\newcommand{\JGTTRenglishkeywords}{""" + en_kw + r"""}
\newcommand{\JGTTRjournalnametr}{""" + escape(jname_tr) + r"""}
\newcommand{\JGTTRjournalnameen}{""" + escape(jname_en) + r"""}
\newcommand{\JGTTRauthorshort}{""" + author_short + r"""}
\newcommand{\JGTTRheadtitle}{""" + head_title + r"""}
\newcommand{\JGTTRaffiliations}{""" + affiliations + r"""}
\newcommand{\JGTTRcorrespondinginfo}{""" + corresponding + r"""}
\newcommand{\JGTTRapacitation}{""" + apa_citation + r"""}
\newcommand{\JGTTRethicsstatement}{""" + ethics + r"""}

% ── DOI yardımcı makrosu (doi: önekini tekrar etmeden hyperlink) ──
\newcommand{\JGTTRdoilink}{\href{https://doi.org/\JGTTRDOI}{\JGTTRDOI}}

% ── Internal helpers ──
\newcommand{\infolabel}[1]{{\fontsize{9}{11}\selectfont\scshape #1}}
\newcommand{\infosubheading}[1]{{\fontsize{7.5}{9}\selectfont\bfseries #1}}
\newcommand{\infovalue}[1]{{\fontsize{7.5}{9}\selectfont #1}}
\newcommand{\infoboldlabel}[1]{{\fontsize{7.5}{9}\selectfont\bfseries #1}}
\newcommand{\inforule}{\par\vspace{0pt}\noindent\rule{\linewidth}{0.4pt}\par\vspace{0pt}}

""" + _first_page_layout(data, js, english_only, has_tr_abs, has_en_abs, bool(authors)) + r"""

% ============================================================
\begin{document}

\JGTTRfirstpage{%
  """ + author_block + r"""%
}
% Kapak sayfası sayfa 1'dir ancak numara gösterilmez.
% İkinci sayfa sayfa 2 olarak başlar.

""" + body_text + '\n\n' + refs_tex + r"""

\end{document}
"""
    if str(cov.get('start_page', '')).isdigit():
        tex = tex.replace(r'\begin{document}', r'\begin{document}' + '\n' +
                          r'\setcounter{page}{' + str(int(cov['start_page'])) + '}')
    tex = tex.replace("% Kapak sayfası sayfa 1'dir ancak numara gösterilmez.\n% İkinci sayfa sayfa 2 olarak başlar.",
                      "% Cover numbering starts from the issue's first article page.")
    if font_name == 'carlito':
        # Carlito has no small-cap face; uppercase labels remain readable.
        tex = tex.replace(r'\scshape', r'\upshape')
    return tex


def build_zip_form(tex_content: str, logo_src: str, figure_file_bytes: dict,
                   journal_settings: dict = None,
                   ccby_src: str = None,
                   ccby_upload: tuple = None) -> bytes:
    """
    Build Overleaf-ready ZIP including:
    - main.tex
    - journal_logo.<ext> (logo)
    - optional explicitly supplied licence graphic
    - figure files (fig_N.ext)
    - README_Overleaf.txt
    """
    js = normalize_settings(journal_settings)
    logo_stem = js.get('logo_stem', 'journal_logo')

    def asset_name(name):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.(png|jpe?g|pdf)', name):
            raise ValueError('Arşivdeki görsel dosyası adı güvenli değil.')
        return name

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('main.tex', tex_content.encode('utf-8'))

        if logo_src and os.path.exists(logo_src):
            # Determine extension of the actual logo file
            ext = logo_src.rsplit('.', 1)[-1].lower() if '.' in logo_src else 'png'
            zf.write(logo_src, asset_name(logo_stem + '.' + ext))

        # An article licence is never assigned by the formatter itself.
        if ccby_upload and ccby_upload[1]:
            ext = ccby_upload[0].rsplit('.', 1)[-1].lower()
            zf.writestr(asset_name(js['cc_logo_stem'] + '.' + ext), ccby_upload[1])
        elif ccby_src and os.path.exists(ccby_src):
            ext = ccby_src.rsplit('.', 1)[-1].lower()
            with open(ccby_src, 'rb') as _f:
                zf.writestr(asset_name(js['cc_logo_stem'] + '.' + ext), _f.read())

        for fkey, (zipname, filebytes) in figure_file_bytes.items():
            zf.writestr(asset_name(zipname), filebytes)

        readme = (
            "AI-ditor Plus — Overleaf Yükleme Rehberi\n"
            "=================================================\n\n"
            "1. Bu ZIP dosyasını açın.\n"
            "2. Overleaf.com → New Project → Upload Project → ZIP'i seçin.\n"
            "3. Menu → Compiler → XeLaTeX seçin.\n"
            "4. Recompile → PDF hazır.\n"
        )
        zf.writestr('README_Overleaf.txt', readme.encode('utf-8'))

    buf.seek(0)
    return buf.read()
