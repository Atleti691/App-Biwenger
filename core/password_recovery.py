import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetConfirmView
from django.db.models import Q
from django.urls import reverse_lazy
from django.utils import timezone

from .models import ContactoManager, UserAccess

logger = logging.getLogger(__name__)


class LeaguePasswordResetForm(PasswordResetForm):
    def clean_email(self):
        return self.cleaned_data['email'].strip()

    def get_users(self, email):
        # Legacy staff accounts may only have their email in Communications.
        managers = ContactoManager.objects.filter(email__iexact=email).values_list('manager', flat=True)
        matches = Q(email__iexact=email)
        for manager in managers:
            matches |= Q(username__iexact=manager, email='')
        users = get_user_model().objects.filter(matches, is_active=True).distinct()
        eligible = [user for user in users if user.has_usable_password()]
        logger.info('Recuperación de contraseña: %s cuenta(s) activa(s) encontrada(s)', len(eligible))
        return eligible

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        try:
            super().send_mail(
                subject_template_name, email_template_name, context, from_email,
                self.cleaned_data['email'], html_email_template_name,
            )
        except Exception:
            logger.exception('Error al enviar el correo de recuperación de contraseña')
            raise


class LeaguePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        response = super().form_valid(form)
        UserAccess.objects.filter(user=self.user).update(
            must_change_password=False, password_changed_at=timezone.now()
        )
        return response
