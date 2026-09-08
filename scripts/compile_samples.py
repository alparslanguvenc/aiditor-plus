"""Compile real sample articles for layout QA. Requires XeLaTeX or Tectonic."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from formatter import generate_latex_from_form
from journal_templates import TEMPLATES
from test_formatter_templates import sample_article


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.qa' / 'pdf')
    parser.add_argument('--engine', default=shutil.which('xelatex') or shutil.which('tectonic'))
    parser.add_argument('--extended', action='store_true')
    args = parser.parse_args()
    if not args.engine:
        parser.error('Use --engine /path/to/xelatex or tectonic')
    cases = [(tpl['id'], tpl['settings'], sample_article()) for tpl in TEMPLATES]
    if args.extended:
        for font in ['texgyrepagella','texgyretermes','texgyrebonum','texgyreheros','carlito','latinmodern']:
            cases.append(('font-'+font, dict(font_family=font), sample_article()))
        for fit in ['auto','compact','dense']:
            article=sample_article()
            article['cover']['first_page_fit']=fit
            article['abstract']['tr_abs'] *= 2
            article['abstract']['en_abs'] *= 2
            cases.append(('dense-'+fit, {}, article))
        article=sample_article();article['cover']['title_note']=''
        cases.append(('english', dict(english_only=True,template_id='contemporary'), article))
    report=[]
    for name, settings, data in cases:
        directory=args.output.resolve()/name;directory.mkdir(parents=True, exist_ok=True)
        settings=dict(settings,journal_name_tr='Akademik Araştırmalar Dergisi',
                      journal_name_en='Journal of Academic Research',journal_url='https://example.org/journal',
                      issn_online='1234-5678',footer_text='Örnek dergi yayını · Example journal publication')
        from PIL import Image, ImageDraw
        logo=Image.new('RGB',(180,180),'white');draw=ImageDraw.Draw(logo)
        draw.rectangle((12,12,168,168),outline=settings.get('accent_color','#244E63'),width=6)
        draw.text((90,88),'AJ',anchor='mm',fill=settings.get('accent_color','#244E63'),font_size=60)
        logo.save(directory/'journal_logo.png')
        tex=generate_latex_from_form(copy.deepcopy(data),{},settings)
        (directory/'main.tex').write_text(tex,encoding='utf-8')
        command=[args.engine,'-k','--keep-logs','main.tex'] if 'tectonic' in Path(args.engine).name else [args.engine,'-interaction=nonstopmode','-halt-on-error','main.tex']
        output=subprocess.run(command,cwd=directory,capture_output=True,text=True,timeout=240)
        (directory/'compile.log').write_text(output.stdout+output.stderr,encoding='utf-8')
        if output.returncode or not (directory/'main.pdf').exists():
            raise RuntimeError(f'{name}: PDF compilation failed; see {directory / "compile.log"}')
        import pdfplumber
        with pdfplumber.open(directory/'main.pdf') as doc:
            text='\n'.join(page.extract_text() or '' for page in doc.pages)
            if 'Giriş' not in text and 'Introduction' not in text:
                raise AssertionError(f'{name}: article body missing')
            if 'Examplejournalpublication' not in ''.join(text.split()):
                raise AssertionError(f'{name}: custom footer missing')
            if 'JGTTR' in text or 'Global Tourism' in text:
                raise AssertionError(f'{name}: unrelated journal branding leaked')
            first=doc.pages[0]
            first.to_image(resolution=110).save(directory/'first-page.png')
            report.append(dict(case=name,pages=len(doc.pages),size=(directory/'main.pdf').stat().st_size))
        print(f'PASS {name}: {report[-1]["pages"]} pages',flush=True)
    args.output.joinpath('report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
