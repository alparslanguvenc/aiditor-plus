"""Reference-manager citations survive import; suggested citations carry DOI and journal choice."""
import io
import json
import unittest

from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from citation_links import citation_report
from docx_export import generate_docx_from_form
from formatter import extract_form_data_from_docx, generate_latex_from_form
from journal_templates import TEMPLATES, normalize_settings
from page_furniture import citation_text, running_slots
from test_formatter_templates import sample_article

PANEL = next(item['settings'] for item in TEMPLATES if item['id'] == 'bilingual_panel')
NAMES = {'journal_name_tr': 'Örnek Sosyal Araştırmalar Dergisi', 'journal_name_en': 'Journal of Sample Social Research'}


def _run(text, tag='w:t'):
    run = OxmlElement('w:r'); node = OxmlElement(tag)
    node.set(qn('xml:space'), 'preserve'); node.text = text; run.append(node)
    return run


def _fld(kind):
    run = OxmlElement('w:r'); node = OxmlElement('w:fldChar'); node.set(qn('w:fldCharType'), kind); run.append(node)
    return run


def zotero_field(paragraph, shown):
    code = ' ADDIN ZOTERO_ITEM CSL_CITATION ' + json.dumps({'properties': {'formattedCitation': shown}}, ensure_ascii=False)
    for node in (_fld('begin'), _run(code, 'w:instrText'), _fld('separate'), _run(shown), _fld('end')):
        paragraph._p.append(node)


def simple_field(paragraph, shown):
    paragraph._p.append(parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr=" ADDIN ZOTERO_ITEM CSL_CITATION {{}} ">'
                                  f'<w:r><w:t xml:space="preserve">{shown}</w:t></w:r></w:fldSimple>'))


def content_control(paragraph, shown, placeholder=False):
    flag = '<w:showingPlcHdr/>' if placeholder else ''
    paragraph._p.append(parse_xml(f'<w:sdt {nsdecls("w")}><w:sdtPr><w:tag w:val="MENDELEY_CITATION_v3"/>{flag}</w:sdtPr>'
                                  f'<w:sdtContent><w:r><w:t xml:space="preserve">{shown}</w:t></w:r></w:sdtContent></w:sdt>'))


def manuscript():
    document = Document()
    document.add_paragraph('Kırsal Turizmde Dijital Tanıtım', style='Title')
    document.add_paragraph('Öz')
    document.add_paragraph('Bu çalışma kısa bir örnek özet içermektedir ve test içindir.')
    document.add_heading('Giriş', level=1)
    p = document.add_paragraph('Karmaşık alan '); zotero_field(p, '(Yılmaz, 2020)'); p.add_run('.')
    p = document.add_paragraph('Basit alan '); simple_field(p, '(Kaya ve Demir, 2021)'); p.add_run(' ile.')
    p = document.add_paragraph('İçerik denetimi '); content_control(p, '(Smith vd., 2022)'); p.add_run(' çerçevesi.')
    p = document.add_paragraph('Boş denetim '); content_control(p, 'Metin girmek için tıklayın', placeholder=True); p.add_run('sonu.')
    p = document.add_paragraph('İzlenen değişiklik ')
    p._p.append(parse_xml(f'<w:del {nsdecls("w")} w:id="1" w:author="x"><w:r><w:delText>silinen</w:delText></w:r></w:del>'))
    p._p.append(parse_xml(f'<w:ins {nsdecls("w")} w:id="2" w:author="x"><w:r><w:t xml:space="preserve">eklenen (Yılmaz, 2020)</w:t></w:r></w:ins>'))
    document.add_heading('Kaynakça', level=1)
    for reference in ['Kaya, B., & Demir, C. (2021). Çevrim içi görünürlük. Örnek Dergi, 5(1), 20–34.',
                      'Smith, J., Brown, L., & Green, P. (2022). Digital tools. Example Journal, 12(3), 101–118.',
                      'Yılmaz, A. (2020). Kırsal kalkınma ve turizm. Örnek Yayınevi.']:
        document.add_paragraph(reference)
    stream = io.BytesIO(); document.save(stream)
    return extract_form_data_from_docx(stream.getvalue())[0]


class ReferenceManagerImportTests(unittest.TestCase):
    def setUp(self):
        self.data = manuscript()
        self.text = self.data['sections'][0]['content']

    def test_field_and_content_control_citations_are_kept(self):
        for citation in ('(Yılmaz, 2020)', '(Kaya ve Demir, 2021)', '(Smith vd., 2022)'):
            self.assertIn(citation, self.text)
        self.assertNotIn('ZOTERO_ITEM', self.text)

    def test_placeholders_and_deleted_text_are_left_out(self):
        self.assertIn('Boş denetim sonu.', self.text)
        self.assertNotIn('tıklayın', self.text)
        self.assertIn('İzlenen değişiklik eklenen (Yılmaz, 2020)', self.text)
        self.assertNotIn('silinen', self.text)

    def test_imported_citations_link_to_references(self):
        self.assertEqual(citation_report(self.data)['linked_in_body'], 4)


class SuggestedCitationTests(unittest.TestCase):
    def test_turkish_journal_name_and_doi_by_default(self):
        settings = normalize_settings({**PANEL, **NAMES})
        text = citation_text(sample_article(), settings)
        self.assertIn('Örnek Sosyal Araştırmalar Dergisi, 4(2), 89–104.', text)
        self.assertTrue(text.endswith(' https://doi.org/10.1234/example.2026.4'))
        tex = generate_latex_from_form(sample_article(), {}, {**PANEL, **NAMES})
        citation = tex[tex.index(r'\newcommand{\JGTTRapacitation}'):].split('\n', 1)[0]
        self.assertIn(r'\textit{Örnek Sosyal Araştırmalar Dergisi}', citation)
        self.assertIn(r'\href{https://doi.org/\JGTTRDOI}{https://doi.org/\JGTTRDOI}', citation)

    def test_english_journal_name_can_be_chosen(self):
        settings = normalize_settings({**NAMES, 'citation_journal_name': 'english'})
        self.assertIn('Journal of Sample Social Research, 4(2)', citation_text(sample_article(), settings))
        english_only = normalize_settings({**NAMES, 'english_only': True})
        self.assertIn('Journal of Sample Social Research', citation_text(sample_article(), english_only))
        tex = generate_latex_from_form(sample_article(), {}, {**NAMES, 'citation_journal_name': 'english'})
        self.assertIn(r'\textit{Journal of Sample Social Research}', tex[tex.index(r'\newcommand{\JGTTRapacitation}'):])
        with self.assertRaises(ValueError):
            normalize_settings({'citation_journal_name': 'german'})

    def test_doi_is_omitted_when_missing_and_from_running_headers(self):
        data = sample_article(); data['cover']['doi'] = ''
        self.assertNotIn('doi.org', citation_text(data, normalize_settings(NAMES)))
        header = running_slots(normalize_settings(NAMES), sample_article(), 'header', 'odd')[1]
        self.assertNotIn('doi.org', header)

    def test_bilingual_panel_word_citation_has_doi_and_turkish_name(self):
        settings = {**PANEL, **NAMES, 'citation_position': 'below_authors'}
        doc = Document(io.BytesIO(generate_docx_from_form(sample_article(), {}, settings)))
        citation = next(p for p in doc.paragraphs if p.text.startswith('Önerilen Atıf'))
        self.assertIn('Örnek Sosyal Araştırmalar Dergisi', citation.text)
        self.assertTrue(citation.text.endswith('https://doi.org/10.1234/example.2026.4'))
        self.assertIn('w:hyperlink', citation._p.xml)


if __name__ == '__main__':
    unittest.main()
