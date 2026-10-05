from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from .clause_data import missing_clause_details
from .models import JornadaRegistro, UserAccess


class ClauseReviewUnitTests(SimpleTestCase):
    def test_only_totals_without_detail_are_flagged(self):
        data = {'Missing': {'money': '127.500 €', 'penalty': '2', 'clauses': []},
                'Penalty': {'penalty': '2'},
                'Good': {'money': '100 €', 'clauses': [{'to': 'Other', 'value': 1000}]},
                'Legacy': {'penalty': '2', 'clauses': [1000]},
                'Zero': {'money': '0 €', 'penalty': '0', 'clauses': []},
                'Empty': {'app': '25'}}
        self.assertEqual([row['manager'] for row in missing_clause_details(data)], ['Missing', 'Penalty'])
        self.assertEqual(data['Missing']['clauses'], [])


class ClauseReviewPageTests(TestCase):
    def test_latest_record_only_and_read_only(self):
        user = get_user_model().objects.create_user('reviewer', password='test')
        access = UserAccess.objects.create(user=user, role='admin')
        old_user = get_user_model().objects.create_user('older')
        old_access = UserAccess.objects.create(user=old_user)
        JornadaRegistro.objects.create(user_access=old_access, season=2026, jornada=2,
            division='Segunda División', datos={'Old': {'penalty': '2'}})
        current = JornadaRegistro.objects.create(user_access=access, season=2026, jornada=2,
            division='Segunda División', cerrada=True,
            datos={'Marina': {'money': '4568 €', 'clauses': [], 'penalty': '2'},
                   'Correct': {'clauses': [500], 'penalty': '2'}})
        self.client.force_login(user)
        response = self.client.get('/resumen-jornadas/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['clause_review_managers'], 1)
        self.assertContains(response, 'Marina')
        self.assertContains(response, '4568 €')
        self.assertNotContains(response, '>Old<')
        current.refresh_from_db()
        self.assertEqual(current.datos['Marina']['clauses'], [])
        self.assertTrue(current.cerrada)
