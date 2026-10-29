import importlib
from datetime import timedelta
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CambioRegistro, UserAccess


class AccessExpiryTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('Atleti69')
        UserAccess.objects.create(user=self.admin, role='admin', must_change_password=False)
        self.user = get_user_model().objects.create_user('Checo21', password='TestOnlyPassword123!')
        self.account = UserAccess.objects.create(user=self.user, role='viewer', is_viewer=True,
            must_change_password=False, access_expires_at=timezone.now()-timedelta(days=1))

    def test_expired_login_explains_reason_without_starting_session(self):
        response = self.client.post(reverse('login'), {'username': 'Checo21', 'password': 'TestOnlyPassword123!'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tu acceso ha caducado.')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.last_login)
        response = self.client.post(reverse('login'), {'username': 'Checo21', 'password': 'incorrecta'})
        self.assertNotContains(response, 'Tu acceso ha caducado.')
        self.assertContains(self.client.get('/login/?expired=1'), 'Tu acceso ha caducado.')

    def test_clear_expiry_preserves_account_password_permissions_and_other_users(self):
        other = get_user_model().objects.create_user('OtherViewer')
        other_access = UserAccess.objects.create(user=other, role='viewer', access_expires_at=self.account.access_expires_at)
        password = self.user.password
        self.client.force_login(self.admin)
        response = self.client.post(reverse('communications'), {'action': 'clear_access_expiry', 'account_id': self.account.pk})
        self.assertContains(response, 'Acceso de Checo21 sin caducidad.')
        self.account.refresh_from_db()
        self.user.refresh_from_db()
        other_access.refresh_from_db()
        self.assertIsNone(self.account.access_expires_at)
        self.assertIsNotNone(other_access.access_expires_at)
        self.assertEqual(self.user.password, password)
        self.assertEqual(self.account.role, 'viewer')
        self.assertTrue(self.account.is_viewer)
        self.assertFalse(self.account.must_change_password)
        self.assertEqual(CambioRegistro.objects.filter(accion='quitar caducidad de acceso').count(), 1)
        self.client.post(reverse('communications'), {'action': 'clear_access_expiry', 'account_id': self.account.pk})
        self.assertEqual(CambioRegistro.objects.filter(accion='quitar caducidad de acceso').count(), 1)
        self.client.logout()
        response = self.client.post(reverse('login'), {'username': 'Checo21', 'password': 'TestOnlyPassword123!'}, follow=True)
        self.assertNotContains(response, 'Tu acceso ha caducado.')
        self.assertIn('_auth_user_id', self.client.session)

    def test_expiry_column_and_button_are_visible_for_temporary_accounts(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('communications'))
        self.assertContains(response, 'Vigencia del acceso')
        self.assertContains(response, '⛔ Acceso caducado')
        self.assertContains(response, '🔓 Quitar caducidad')

    def test_unauthorized_or_csrf_missing_requests_cannot_remove_expiry(self):
        self.client.force_login(self.user)
        self.client.post(reverse('communications'), {'action': 'clear_access_expiry', 'account_id': self.account.pk})
        self.account.refresh_from_db()
        self.assertIsNotNone(self.account.access_expires_at)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(reverse('communications'), {'action': 'clear_access_expiry', 'account_id': self.account.pk}).status_code, 403)
        self.account.refresh_from_db()
        self.assertIsNotNone(self.account.access_expires_at)

    def test_checo_migration_is_targeted_and_idempotent(self):
        other = get_user_model().objects.create_user('OtherViewer')
        other_access = UserAccess.objects.create(user=other, role='viewer', access_expires_at=self.account.access_expires_at)
        migration = importlib.import_module('core.migrations.0027_checo21_permanent_viewer')
        before = get_user_model().objects.values().get(pk=self.user.pk)
        migration.clear_checo_expiry(apps, SimpleNamespace(connection=connection))
        migration.clear_checo_expiry(apps, SimpleNamespace(connection=connection))
        self.account.refresh_from_db()
        other_access.refresh_from_db()
        self.assertIsNone(self.account.access_expires_at)
        self.assertIsNotNone(other_access.access_expires_at)
        self.assertEqual(get_user_model().objects.values().get(pk=self.user.pk), before)
        self.assertEqual(CambioRegistro.objects.filter(accion='quitar caducidad de acceso').count(), 1)

    def test_new_accounts_have_no_expiry_by_default(self):
        other = get_user_model().objects.create_user('NewViewer')
        account = UserAccess.objects.create(user=other, role='viewer')
        self.assertIsNone(account.access_expires_at)
