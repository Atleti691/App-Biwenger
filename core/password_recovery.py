from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import reverse_lazy
from django.utils import timezone

from .models import UserAccess


class LeaguePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        response = super().form_valid(form)
        UserAccess.objects.filter(user=self.user).update(
            must_change_password=False, password_changed_at=timezone.now()
        )
        return response
