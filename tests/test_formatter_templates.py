"""Journal layouts, safe settings and source-faithful manuscript regression tests."""
import copy
import io
import unittest
import zipfile

from formatter import generate_latex_from_form, _build_figtable_latex, build_zip_form, _normalize_table_model, _parse_table_rows
from journal_templates import TEMPLATES, default_settings, normalize_settings


def sample_article():
    """Shared compilation fixture: bilingual metadata, authors, abstract and rich table."""
    return {
        'cover': {
            'tr_title': 'Akademik Yayıncılıkta Açık ve Tekrarlanabilir İş Akışları',
            'en_title': 'Open and Reproducible Workflows in Academic Publishing',
            'year': '2026', 'volume': '4', 'issue': '2', 'start_page': '89', 'end_page': '104',
            'doi': '10.1234/example.2026.4', 'article_type': 'Araştırma Makalesi / Research Article',
            'received': '14.03.2026', 'accepted': '22.07.2026', 'published': '08.09.2026',
            'editor': 'Dr. Deniz Örnek', 'ethics': 'Bu örnek makalede insan katılımcılardan veri toplanmamıştır.',
            'title_note': 'Örnek makale: sayfa düzenini göstermek amacıyla hazırlanmıştır.',
        },
        'authors': [
            {'name': 'Deniz Örnek', 'affiliation': 'Örnek Üniversitesi, Sosyal Bilimler Bölümü',
             'email': 'deniz@example.org', 'corresponding': True},
            {'name': 'Alex Smith', 'affiliation': 'Example University, Department of Information Studies',
             'email': 'alex@example.org'},
        ],
        'abstract': {
            'tr_abs': ('Bu çalışma, akademik dergilerde düzenli ve tekrarlanabilir yayın süreçlerinin '
                       'nasıl kurulabileceğini incelemektedir. Editörlerin kullandığı sayfa düzenleri, '
                       'kaynak belgelerin yapısı ve makale üst verileri birlikte ele alınmaktadır. '
                       'Örnek iş akışı, kaynak bilgilerin korunması ve dergi tercihleriyle tutarlı '
                       'bir çıktı oluşturulması üzerine kurulmuştur. Bulgular, ortak bir biçimlendirme '
                       'altyapısının dergilere özgü tasarımlar ile birlikte kullanılabileceğini göstermektedir.'),
            'en_abs': ('This study examines the development of consistent and reproducible workflows '
                       'for academic journals. Page layouts, source document structure and article '
                       'metadata are considered together. The example workflow focuses on preserving '
                       'source information while producing output consistent with journal preferences. '
                       'The findings illustrate how a shared formatting system can accommodate '
                       'the distinct visual identity of different publications.'),
            'tr_kw': 'akademik yayıncılık; dergi editörlüğü; açık bilim',
            'en_kw': 'academic publishing; journal editing; open science',
        },
        'sections': [{'id': 'introduction', 'name': 'Giriş / Introduction', 'level': '1',
                      'content': 'Editoryal çalışmalar, kaynak belgelerin düzenli ve izlenebilir biçimde işlenmesini gerektirir.\n\n'
                                 'Bu örnek makale, farklı dergi şablonlarında aynı içeriğin nasıl gösterildiğini sunmaktadır.'},
                     {'id': 'results', 'name': 'Bulgular / Results', 'level': '1',
                      'content': 'Tablo 1, örnek editoryal iş akışının aşamalarını göstermektedir.'}],
        'figtables': [{'type': 'table', 'number': '1', 'section_id': 'results', 'section': 'Bulgular / Results',
                       'tr_cap': 'Örnek iş akışı', 'en_cap': 'Example workflow', 'float_placement': 'exact',
                       'tbl_model': {'header_rows': 1, 'column_widths': [0.35, 0.65], 'grid_borders': True,
                                     'rows': [[{'text': 'Aşama / Stage', 'bold': True}, {'text': 'İşlem / Action', 'bold': True}],
                                              [{'text': '1. İçeri aktarma'}, {'text': 'Word belgesinin bölüm, tablo ve şekillerini koruma'}],
                                              [{'text': '2. Dergi biçimi'}, {'text': 'Ön ayarların makaleye uygulanması'}],
                                              [{'text': '3. Son kontrol'}, {'text': 'PDF ve kaynak dosyanın gözden geçirilmesi'}]]}}],
        'extra': {}, 'references': 'Örnek, D. (2026). Akademik yayıncılıkta iş akışları. Örnek Yayınları.',
    }


class SettingsTests(unittest.TestCase):
    def test_defaults_are_independent_and_neutral(self):
        first = default_settings(); first['journal_name_tr'] = 'Changed'
        self.assertEqual(default_settings()['journal_name_tr'], '')
        self.assertEqual(default_settings()['journal_url'], '')
        self.assertEqual(default_settings()['issn_print'], '')
        self.assertNotIn('jgttr', str(default_settings()).lower())

    def test_presets_validate_and_legacy_fonts_migrate(self):
        self.assertEqual({t['id'] for t in TEMPLATES}, {'classic', 'contemporary', 'centered', 'minimal'})
        for template in TEMPLATES:
            self.assertEqual(normalize_settings(template['settings'])['template_id'], template['id'])
        self.assertEqual(normalize_settings({'font': 'Times New Roman'})['font_family'], 'texgyretermes')
        self.assertEqual(normalize_settings({'header_layout': 'minimal'})['template_id'], 'minimal')

    def test_malformed_or_latex_injectable_preferences_are_rejected(self):
        for field, value in [
            ('template_id', 'unknown'), ('footer_layout', 'all'), ('accent_color', 'red}\\input{x}'),
            ('journal_url', 'javascript:alert(1)'), ('journal_url', 'https://user:pass@example.org'),
            ('journal_url', 'https://example.org/bad path'), ('font_family', '}\\input{x}'),
            ('logo_stem', '../../password'), ('cc_logo_stem', '\\write18'), ('body_size', 72),
            ('logo_height_cm', float('nan')), ('logo_height_cm', True), ('logo_height_cm', 4),
            ('english_only', 'false'), ('journal_name_tr', ['journal']), ('footer_text', 'x' * 3001),
        ]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                normalize_settings({field: value})


class TemplateOutputTests(unittest.TestCase):
    def test_layouts_have_distinct_structure_and_custom_identity(self):
        outputs = {}
        for template in TEMPLATES:
            settings = {**template['settings'], 'journal_name_tr': 'Bilim & Toplum',
                        'journal_name_en': 'Science & Society', 'accent_color': '#336699',
                        'footer_text': 'Özel yayıncı dipnotu.', 'issn_online': '1234-567X'}
            tex = generate_latex_from_form(sample_article(), {}, settings)
            self.assertIn('Bilim \\& Toplum', tex)
            self.assertIn('Özel yayıncı dipnotu.', tex)
            self.assertIn(r'\definecolor{JGTTRbrown}{HTML}{336699}', tex)
            self.assertIn('e-ISSN: 1234-567X', tex)
            self.assertNotIn('Journal of Global Tourism', tex)
            self.assertNotIn('2717-6924', tex)
            self.assertIn(r'max totalheight={\dimexpr\textheight-\ht\JGTTRfooterbox', tex)
            outputs[template['id']] = tex[tex.index('% Template:'):]
        self.assertEqual(len(set(outputs.values())), 4)
        self.assertIn(r'p{0.183\textwidth}', outputs['classic'])
        self.assertIn(r'\colorbox{JGTTRbrown}', outputs['contemporary'])
        self.assertIn(r'\begin{minipage}[t]{0.48\textwidth}', outputs['contemporary'])
        self.assertIn(r'{\noindent \centering \fontsize', outputs['centered'])
        self.assertIn(r'\begin{minipage}[c]{0.78\textwidth}', outputs['minimal'])

    def test_all_footer_modes_keep_custom_note_ethics_and_doi(self):
        for mode in ('full', 'compact', 'minimal'):
            tex = generate_latex_from_form(sample_article(), {}, {'footer_layout': mode, 'footer_text': 'Custom footer'})
            foot = tex[tex.index(r'\newcommand{\JGTTRfirstpagefooter}'):tex.index(r'\newcommand{\JGTTRfirstpage}[1]')]
            self.assertIn('Custom footer', foot)
            self.assertIn(r'\JGTTRethicsstatement', foot)
            self.assertIn(r'\JGTTRdoilink', foot)
            self.assertIn(r'\JGTTRaffiliations', foot)
            self.assertEqual(r'\JGTTRapacitation' in foot, mode != 'minimal')

    def test_missing_logos_are_optional_and_can_be_hidden(self):
        tex = generate_latex_from_form(sample_article(), {}, {})
        self.assertIn(r'\IfFileExists{journal_logo.png}', tex)
        self.assertIn(r'\IfFileExists{license_logo.png}', tex)
        hidden = generate_latex_from_form(sample_article(), {}, {'show_logo': False, 'show_cc_logo': False})
        self.assertNotIn(r'\includegraphics[height=', hidden)

    def test_density_profile_and_numbering(self):
        article = sample_article()
        for mode, font in [('compact', '{12.3}{14.3}'), ('dense', '{11.7}{13.5}')]:
            tex = generate_latex_from_form(article, {}, {'first_page_fit': mode})
            self.assertIn('First-page density profile: ' + mode, tex)
            self.assertIn(r'\fontsize' + font, tex)
            self.assertIn(r'\setcounter{page}{89}', tex)
        article['abstract']['en_abs'] = 'A long abstract. ' * 400
        self.assertIn('First-page density profile: dense', generate_latex_from_form(article, {}, {}))

    def test_english_output_correspondence_and_no_fabricated_declarations(self):
        article = sample_article()
        tex = generate_latex_from_form(article, {}, {'english_only': True, 'corresponding_marker': '†'})
        cover = tex[tex.index('% Template:'):]
        self.assertNotIn('MAKALE BİLGİSİ', cover)
        self.assertNotIn('Sorumlu yazar', cover)
        self.assertIn(r'\ensuremath{\dagger} Corresponding author', cover)
        self.assertIn(r'\newcommand{\JGTTRauthorshort}{Örnek \& Smith}', tex)
        self.assertIn('\\\\\n  \\textsuperscript{2}', tex)
        self.assertNotIn(r'\textbackslash{}\&', tex)
        empty = generate_latex_from_form({'cover': {}, 'abstract': {}, 'authors': []}, {}, {})
        for invented in ('relevant ethics committee decision', 'declare no conflict', 'Author One', r'\begin{list}'):
            self.assertNotIn(invented, empty)

    def test_duplicate_deleted_and_renamed_sections_preserve_table_placement(self):
        article = sample_article()
        article['sections'] = [{'id': 'a', 'name': 'Results', 'content': 'First marker.'},
                               {'id': 'b', 'name': 'Results', 'content': 'Second marker.'}]
        article['figtables'] = [
            {'type': 'table', 'number': '1', 'section_id': 'b', 'section': 'Old title', 'tbl_data': 'Title\tValue\nB\t1'},
            {'type': 'table', 'number': '2', 'section_id': 'deleted', 'section': 'Old', 'tbl_data': 'Title | Value\nC | 2'},
        ]
        tex = generate_latex_from_form(article, {}, {})
        self.assertGreater(tex.index(r'\label{tbl1}'), tex.index('Second marker.'))
        self.assertEqual(tex.count(r'\label{tbl2}'), 1)

    def test_table_before_first_paragraph_keeps_source_order(self):
        article = sample_article()
        article['sections'] = [{'name': '2. Results', 'level': '1', 'content': 'Paragraph following the table.'}]
        article['figtables'] = [{'type': 'table', 'number': '1', 'section': '2. Results',
                                 'placement': 'section_start', 'tbl_data': 'A | B\n1 | 2'}]
        tex = generate_latex_from_form(article, {}, {})
        self.assertLess(tex.index(r'\label{tbl1}'), tex.index('Paragraph following the table.'))
        self.assertEqual(tex.count(r'\label{tbl1}'), 1)

    def test_long_footer_can_use_space_left_by_short_abstract(self):
        article = sample_article()
        article['abstract'] = {'en_abs': 'Short abstract.'}
        article['cover']['ethics'] = 'A detailed supplied declaration. ' * 150
        tex = generate_latex_from_form(article, {}, {'english_only': True})
        self.assertIn(r'max totalheight=0.60\textheight', tex)
        self.assertEqual(tex.count('A detailed supplied declaration.'), 150)

    def test_tsv_csv_markdown_tables_and_exact_figures(self):
        for source in ('Name\tValue\nA & B\t25%', 'Name,Value\nA & B,25%', '| Name | Value |\n|---|---|\n| A & B | 25% |'):
            tex = _build_figtable_latex({'type': 'table', 'tbl_data': source}, {})
            self.assertIn(r'A \& B', tex)
            self.assertIn(r'25\%', tex)
            self.assertNotIn('---', tex)
        figure = _build_figtable_latex({'type': 'figure', 'file_key': 'f', 'float_placement': 'exact'}, {'f': 'fig_1'})
        self.assertIn(r'\begin{figure}[H]', figure)
        self.assertIn('height=0.56', figure)

    def test_empty_excel_edge_cells_and_oversize_tables_do_not_lose_data(self):
        self.assertEqual(_parse_table_rows('\tMiddle\t\nA\tB\tC'), [['', 'Middle', ''], ['A', 'B', 'C']])
        with self.assertRaisesRegex(ValueError, '500'):
            _normalize_table_model({'tbl_model': {'rows': [[{'text': str(i)}] for i in range(501)]}})

    def test_archive_has_no_implicit_article_license_or_jgttr_assets(self):
        output = build_zip_form('safe tex', '', {}, {})
        with zipfile.ZipFile(io.BytesIO(output)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {'main.tex', 'README_Overleaf.txt'})
        with self.assertRaises(ValueError):
            build_zip_form('tex', '', {'x': ('../fig.png', b'data')}, {})


if __name__ == '__main__':
    unittest.main()
