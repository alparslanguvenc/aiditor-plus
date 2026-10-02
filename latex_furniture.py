"""Render validated running-page settings without accepting raw TeX commands."""
from page_furniture import RUNNING_DEFAULTS, article_values, block_height_cm, resolved_parts, running_slots


def apply_running_latex(tex: str, data: dict, settings: dict, escape) -> str:
    scholarly = settings['template_id'] == 'scholarly'
    if not scholarly and all(settings[key] == value for key, value in RUNNING_DEFAULTS.items()):
        return tex
    values = article_values(data, settings)

    def text(value):
        return ''.join(r'\thepage{}' if kind == 'page' else escape(part).replace('\n', r'\newline ') for kind, part in resolved_parts(value, values))

    def block(kind, variant):
        slots = running_slots(settings, data, kind, variant)
        if not any(slots):
            return ''
        size = int(settings[kind + '_font_size'])
        prefix = rf'\fontsize{{{size}}}{{{size * 1.3:g}}}\selectfont '
        if scholarly:
            prefix = r'\renewcommand{\baselinestretch}{1}' + prefix
        if scholarly and kind == 'header':
            prefix += r'\bfseries\itshape '
        if not slots[0] and not slots[2]:
            return r'\parbox[b]{\textwidth}{\centering ' + prefix + text(slots[1]) + r'\strut}'
        parts = []
        widths = (.87, .01, .10) if scholarly and not slots[1] and slots[0] else (.32, .32, .32)
        for value, align, width in zip(slots, (r'\raggedright', r'\centering', r'\raggedleft'), widths):
            parts.append(r'\parbox[b]{' + str(width) + r'\textwidth}{' + prefix + align + ' ' + text(value) + r'\strut}')
        return r'\hfill'.join(parts)

    lines = [r'\pagestyle{fancy}', r'\fancyhf{}']
    for kind, command in [('header', 'head'), ('footer', 'foot')]:
        for variant, parity in [('odd', 'O'), ('even', 'E')]:
            lines.append(r'\fancy' + command + '[C' + parity + ']{' + block(kind, variant) + '}')
        lines.append('\\renewcommand{\\' + command + 'rulewidth}{' + ('0.4pt' if settings[kind + '_rule'] == 'line' and settings[kind + '_mode'] != 'none' else '0pt') + '}')
    lines.append(r'\fancypagestyle{firstpage}{\fancyhf{}')
    for kind, command in [('header', 'head'), ('footer', 'foot')]:
        content = block(kind, 'first')
        lines.append(r'\fancy' + command + '[C]{' + content + '}')
        lines.append('\\renewcommand{\\' + command + 'rulewidth}{' + ('0.4pt' if settings[kind + '_rule'] == 'line' and content else '0pt') + '}')
    lines.append('}')
    start = tex.index('% ── Headers & footers ──')
    end = tex.index('% ── Caption format ──', start)
    tex = tex[:start] + '% Custom running headers and footers\n' + '\n'.join(lines) + '\n\n' + tex[end:]
    tex = tex.replace('pt,a4paper]{article}', 'pt,a4paper,twoside]{article}')
    header_height = block_height_cm(settings, data, 'header')
    footer_height = block_height_cm(settings, data, 'footer') + .4
    layout = f'includehead=true,includefoot=true,top=0.8cm,bottom=0.8cm,left=1.5cm,right=1.5cm,headheight={header_height:.3f}cm,headsep=0.4cm,footskip={footer_height:.3f}cm'
    if scholarly:
        layout = f'includehead=true,includefoot=true,top=1.25cm,bottom=1.4cm,left=2.5cm,right=2.5cm,headheight={header_height:.3f}cm,headsep=0.65cm,footskip={footer_height:.3f}cm'
    elif settings['template_id'] == 'bilingual_panel':
        layout = f'includehead=true,includefoot=true,top=0.6cm,bottom=1.1cm,left=2cm,right=2cm,headheight={header_height:.3f}cm,headsep=0.2cm,footskip={footer_height:.3f}cm'
    tex = tex.replace(r'\geometry{a4paper,top=1.5cm,bottom=1.5cm,left=1.5cm,right=1.5cm,headheight=1.2cm,headsep=0.4cm,footskip=0.8cm}', r'\geometry{a4paper,' + layout + '}')
    cover_layout = layout.replace('top=1.25cm', 'top=0.3cm').replace('headsep=0.65cm', 'headsep=0.25cm').replace('bottom=1.4cm', 'bottom=0.2cm') if scholarly else layout
    tex = tex.replace(r'\newgeometry{includehead=false,top=1.2cm,bottom=1.5cm,left=1.5cm,right=1.5cm,headheight=0pt,headsep=0pt,footskip=0.8cm}', r'\newgeometry{' + cover_layout + '}')
    return tex
