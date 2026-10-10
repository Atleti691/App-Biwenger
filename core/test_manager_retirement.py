from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from .models import CambioRegistro, ContactoManager, JornadaRegistro, ManagerLiga, UserAccess


class ManagerRetirementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('Atleti69')
        self.access = UserAccess.objects.create(user=self.admin, role='admin', must_change_password=False)
        self.manager, _ = ManagerLiga.objects.update_or_create(season=2026, division='Primera RFEF',
            manager='Patontografos F.C', defaults={'activo':True})
        self.contact = ContactoManager.objects.create(division='Primera RFEF', manager='Patontografos F.C',
            email='retired@example.com', provincia='Asturias')
        self.other = ContactoManager.objects.create(division='Primera RFEF', manager='Beagar13',
            email='active@example.com', provincia='Madrid')
        self.history = JornadaRegistro.objects.create(user_access=self.access, season=2026, jornada=1,
            division='Primera RFEF', cerrada=True, datos={'Patontografos F.C':{'app':'45'}})

    def test_target_only_backup_history_and_idempotence(self):
        migration = import_module('core.migrations.0024_retire_patontografos')
        schema = SimpleNamespace(connection=connection)
        migration.retire_manager(apps, schema)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.activo)
        self.assertFalse(ContactoManager.objects.filter(pk=self.contact.pk).exists())
        self.assertTrue(ContactoManager.objects.filter(pk=self.other.pk).exists())
        self.history.refresh_from_db()
        self.assertEqual(self.history.datos, {'Patontografos F.C':{'app':'45'}})
        self.assertTrue(self.history.cerrada)
        audit = CambioRegistro.objects.get(accion='Baja de Patontografos F.C')
        self.assertEqual(audit.detalle['contactos_archivados'][0]['email'], 'retired@example.com')
        migration.retire_manager(apps, schema)
        self.assertEqual(CambioRegistro.objects.filter(accion='Baja de Patontografos F.C').count(), 1)

    def test_communications_excludes_inactive_manager(self):
        self.manager.activo = False
        self.manager.save()
        self.client.force_login(self.admin)
        response = self.client.get('/comunicaciones/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Patontografos F.C')
        self.assertContains(response, 'Beagar13')
        self.assertNotIn(self.contact.id, [row['id'] for row in response.context['pending_accounts']])
