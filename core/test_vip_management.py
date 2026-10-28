from types import SimpleNamespace

from django.test import SimpleTestCase

from .vip_management import penalty_progress


def winner(name, division, done=False, states=()):
    return SimpleNamespace(manager=name, division=division,
        penalty_distribution=[('Destino', 50)] if done else [],
        penalty_emails=[SimpleNamespace(estado=state) for state in states])


class VIPPenaltyProgressTests(SimpleTestCase):
    def test_unique_recipients_denominators_and_pending_first(self):
        people = [winner('Completado A', 'Primera', True, ('enviado', 'entregado', 'enviado')),
                  winner('Pendiente B', 'Segunda', states=('error',)),
                  winner('Pendiente A', 'Primera', states=('enviado',)),
                  winner('Completado B', 'Segunda', True)]
        result = penalty_progress(people, ['Primera', 'Segunda', 'Tercera'])
        self.assertEqual([person.manager for person in people],
            ['Pendiente A', 'Pendiente B', 'Completado A', 'Completado B'])
        self.assertEqual(result['overall'], {'name': 'Total de acertantes', 'total': 4,
            'done': 2, 'pending': 2, 'sent': 2, 'done_percentage': 50, 'sent_percentage': 50, 'unknown': 1})
        self.assertEqual(result['divisions'][0]['sent_percentage'], 100)
        self.assertEqual(result['divisions'][1]['sent_percentage'], 0)
        self.assertEqual(result['divisions'][2]['done_percentage'], 0)
        self.assertEqual(result['divisions'][2]['total'], 0)

    def test_historic_unknown_delivery_failure_and_retry_dont_fake_progress(self):
        people = [winner('Sin registro', 'Primera', True),
                  winner('Sin correo', 'Primera', states=('sin_correo',)),
                  winner('Fallo', 'Primera', states=('error',)),
                  winner('Rechazado', 'Primera', states=('rechazado',)),
                  winner('Reintentos', 'Primera', states=('enviado', 'error', 'enviado'))]
        result = penalty_progress(people, ['Primera'])['overall']
        self.assertEqual(result['done'], 1)
        self.assertEqual(result['sent'], 2)
        self.assertEqual(result['sent_percentage'], 40)
        self.assertEqual(result['unknown'], 1)

    def test_empty_match_and_unknown_division(self):
        result = penalty_progress([], ['Primera'])
        self.assertEqual(result['overall']['done_percentage'], 0)
        self.assertEqual(result['overall']['sent_percentage'], 0)
        result = penalty_progress([winner('Extra', 'División histórica')], ['Primera'])
        self.assertEqual(result['divisions'][1]['total'], 1)
