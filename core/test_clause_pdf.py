from io import BytesIO

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from pypdf import PdfReader

from .clause_pdf import build_clause_pdf, heat_colors, clause_totals
from .models import CambioRegistro, JornadaRegistro, UserAccess


class ClausePDFLayoutTests(SimpleTestCase):
    def test_three_distinct_colors_and_empty(self):
        self.assertEqual(heat_colors(0, 9), ('#eef2f8', '#56647a'))
        self.assertEqual(heat_colors(1, 9)[0], '#f7d4d6')
        self.assertEqual(heat_colors(2, 9)[0], '#f7d4d6')
        self.assertEqual(heat_colors(3, 9)[0], '#d4efda')
        self.assertEqual(heat_colors(4, 9)[0], '#244e8a')
        self.assertEqual(heat_colors(9, 9)[0], '#244e8a')
        self.assertEqual(heat_colors(3, 100), heat_colors(3, 3))

    def test_totals_count_clauses_not_amount_or_relationships(self):
        links = [{'source':'Alex', 'target':'Marina', 'count':2, 'value':5000},
                 {'source':'Alex', 'target':'Raul', 'count':3, 'value':9000},
                 {'source':'Marina', 'target':'Alex', 'count':4, 'value':7000}]
        outgoing, incoming, total = clause_totals(links)
        self.assertEqual(outgoing, {'Alex':5, 'Marina':4})
        self.assertEqual(incoming, {'Marina':2, 'Raul':3, 'Alex':4})
        self.assertEqual(total, 9)
        self.assertEqual(clause_totals([]), ({}, {}, 0))
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(build_clause_pdf(links, 'Primera División', 'General'))).pages)
        for label in ('Total realizadas', 'Total recibidas', 'Frecuencia baja: 1-2', 'Frecuencia media: 3', 'Frecuencia alta: 4 o más', 'MANAGERS QUE RECIBEN'):
            self.assertIn(label, ' '.join(text.split()))

    def test_large_heatmap_and_full_manager_names(self):
        names = [f'Manager número {index:02}' for index in range(20)]
        names[0] = 'Club con nombre muy largo y símbolos & <especiales>'
        links = [{'source': names[index], 'target': names[(index+1)%20], 'count': index%9+1, 'value': 1000000} for index in range(20)]
        reader = PdfReader(BytesIO(build_clause_pdf(links, 'Segunda División', 'Jornada 1AP')))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn(names[0], text)
        self.assertIn('Jornada 1AP', text)
        self.assertIn('Clave de managers', text)
        self.assertGreater(len(reader.pages), 1)
        for page in reader.pages:
            self.assertGreater(float(page.mediabox.width), float(page.mediabox.height))

    def test_manager_export_excludes_unrelated_relationship(self):
        links = [{'source':'Alex', 'target':'Peña & Amigos', 'count':3, 'value':1234567},
                 {'source':'Marina', 'target':'Alex', 'count':1, 'value':2000},
                 {'source':'No relacionado', 'target':'Otro ajeno', 'count':8, 'value':9999}]
        reader = PdfReader(BytesIO(build_clause_pdf(links, 'Primera División', 'Clasificación general', 'Alex')))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn('Peña & Amigos', text)
        self.assertIn('1.234.567', text)
        self.assertIn('Cláusulas recibidas', text)
        self.assertNotIn('No relacionado', text)
        self.assertLess(float(reader.pages[0].mediabox.width), float(reader.pages[0].mediabox.height))

    def test_export_buttons_and_shared_palette_script(self):
        html = render_to_string('statistics.html', {'divisions':['Primera División'], 'jornadas':[1,101]})
        self.assertIn('Exportar a PDF', html)
        self.assertIn("addExport(legend, 'heatmap')", html)
        self.assertIn("addExport(detail, 'manager')", html)
        for count in (1, 5, 9):
            self.assertIn(heat_colors(count, 9)[0], html)
        self.assertNotIn('rgba(224,107,40', html)
        self.assertIn('Quién recibe las cláusulas', html)
        self.assertIn('Total realizadas', html)
        self.assertIn('Total recibidas', html)
        self.assertNotIn('name.slice(0,7)', html)


class ClausePDFEndpointTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('pdf-viewer')
        self.access = UserAccess.objects.create(user=user, role='viewer', must_change_password=False)
        self.client.force_login(user)
        for number, division, target in [(1,'Primera División','Destino uno'), (2,'Primera División','Destino dos'), (1,'Segunda División','Destino otra división')]:
            JornadaRegistro.objects.create(user_access=self.access, season=2026, jornada=number, division=division,
                datos={'Alex': {'app':'10','clauses':[{'to':target,'value':1000}],'penalty':'2'}})

    def get_export(self, **params):
        return self.client.get('/estadisticas/clausulas/pdf/', {'division':'Primera División','mode':'round','jornada':'1', **params})

    def test_scope_round_and_general_and_read_only(self):
        response = self.get_export(kind='manager', manager='Alex')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
        self.assertIn('Destino uno', text)
        self.assertNotIn('Destino dos', text)
        self.assertNotIn('Destino otra división', text)
        response = self.get_export(mode='general', kind='manager', manager='Alex')
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
        self.assertIn('Destino uno', text)
        self.assertIn('Destino dos', text)
        self.assertNotIn('Destino otra división', text)
        self.assertEqual(CambioRegistro.objects.count(), 0)
        self.assertEqual(JornadaRegistro.objects.count(), 3)

    def test_validation_and_authentication(self):
        for params in [{'manager':'No existe', 'kind':'manager'}, {'jornada':'no'}, {'kind':'bad'}, {'mode':'bad'}]:
            self.assertEqual(self.get_export(**params).status_code, 400)
        self.client.logout()
        self.assertEqual(self.get_export(kind='heatmap').status_code, 302)

    def test_heatmap_for_selected_division(self):
        response = self.get_export(kind='heatmap')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('no-store', response['Cache-Control'])
