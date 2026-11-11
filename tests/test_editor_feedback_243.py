"""Editor feedback for 2.4.3: imported DOI, citation punctuation, hyphenation, corresponding author."""
import io
import re
import unittest

from docx import Document

from docx_export import generate_docx_from_form
from formatter import extract_form_data_from_docx, generate_latex_from_form
from journal_templates import TEMPLATES, normalize_settings
from page_furniture import citation_text
from test_formatter_templates import sample_article

SCHOLARLY = next(item['settings'] for item in TEMPLATES if item['id'] == 'scholarly')


def imported(*front, references=(), header=''):
    document = Document()
    if header:
        document.sections[0].header.paragraphs[0].text = header
    document.add_paragraph('Kırsal Turizmde Dijital Tanıtım', style='Title')
    for text in front:
        document.add_paragraph(text)
    document.add_paragraph('Öz')
    document.add_paragraph('Bu çalışma kısa bir örnek özet içermektedir ve test içindir.')
    document.add_heading('Giriş', level=1)
    document.add_paragraph('Giriş metni (Yılmaz, 2020) burada yer alır; bkz. doi: 10.9999/body.citation.')
    document.add_heading('Kaynakça', level=1)
    for reference in references:
        document.add_paragraph(reference)
    stream = io.BytesIO(); document.save(stream)
    return extract_form_data_from_docx(stream.getvalue())[0]


class ImportedDoiTests(unittest.TestCase):
    def test_labelled_front_matter_doi_is_imported(self):
        data = imported('Araştırma Makalesi', 'DOI: 10.1234/osad.2026.012')
        self.assertEqual(data['cover']['doi'], '10.1234/osad.2026.012')
        self.assertTrue(any('DOI' in warning and '10.1234/osad.2026.012' in warning for warning in data['warnings']))

    def test_doi_link_in_page_header_is_imported(self):
        data = imported(header='Örnek Dergi · https://doi.org/10.5555/ornek.45.')
        self.assertEqual(data['cover']['doi'], '10.5555/ornek.45')

    def test_body_and_reference_dois_are_ignored(self):
        data = imported(references=['Yılmaz, A. (2020). Başlık. Dergi, 1(1), 1–2. https://doi.org/10.1111/ref.1'])
        self.assertNotIn('doi', data['cover'])
        self.assertTrue(any('ile DOI' in warning for warning in data['warnings']))


class CitationPunctuationTests(unittest.TestCase):
    def test_apa_comma_after_journal_and_no_placeholders(self):
        settings = normalize_settings({'journal_name_tr': 'Örnek Dergi'})
        data = sample_article()
        self.assertIn('Örnek Dergi, 4(2), 89–104. https://doi.org/', citation_text(data, settings))
        data['cover'].update(volume='x', issue='x')
        text = citation_text(data, settings)
        self.assertIn('Örnek Dergi, 89–104.', text)
        self.assertNotIn('(x)', text)
        tex = generate_latex_from_form(data, {}, {'journal_name_tr': 'Örnek Dergi'})
        citation = tex[tex.index(r'\newcommand{\JGTTRapacitation}'):].split('\n', 1)[0]
        self.assertIn(r'\textit{Örnek Dergi}, 89--104.', citation)
        self.assertNotIn('(x)', citation)


class HyphenationTests(unittest.TestCase):
    def test_hyphenation_stays_on_by_default_and_can_be_turned_off(self):
        self.assertIn('\\hyphenpenalty=50\n', generate_latex_from_form(sample_article(), {}, {}))
        tex = generate_latex_from_form(sample_article(), {}, {'hyphenation': 'off'})
        self.assertIn('\\hyphenpenalty=10000\n', tex)
        self.assertIn('\\tolerance=2000\n', tex)
        with self.assertRaises(ValueError):
            normalize_settings({'hyphenation': 'auto'})


class CorrespondingAuthorTests(unittest.TestCase):
    def info(self, settings):
        tex = generate_latex_from_form(sample_article(), {}, settings)
        return re.search(r'\\newcommand\{\\JGTTRcorrespondinginfo\}\{(.*)\}\n', tex).group(1)

    def test_full_details_by_default(self):
        self.assertIn('Örnek Üniversitesi', self.info({}))

    def test_name_and_email_only(self):
        info = self.info({'corresponding_detail': 'name_email'})
        self.assertTrue(info.startswith('Deniz Örnek. E-posta:'))
        self.assertIn('deniz@example.org', info)
        self.assertNotIn('Örnek Üniversitesi', info)
        data = sample_article(); data['authors'][0]['orcid'] = '0000-0002-1825-0097'
        footer = Document(io.BytesIO(generate_docx_from_form(data, {}, {**SCHOLARLY, 'corresponding_detail': 'name_email'})))
        line = next(p.text for p in footer.sections[0].first_page_footer.paragraphs if 'Corresponding' in p.text)
        self.assertIn('deniz@example.org', line)
        self.assertNotIn('orcid', line)


if __name__ == '__main__':
    unittest.main()
