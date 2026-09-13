from getpass import getpass

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.models import UserAccess


class Command(BaseCommand):
    help = 'Crea o actualiza las cuentas iniciales de los colaboradores.'

    colaboradores = ['Kabes Team', 'LLull Team', 'Reventao', 'Carbayon']

    def handle(self, *args, **options):
        User = get_user_model()
        for username in self.colaboradores:
            password = getpass(f'Contraseña inicial para {username}: ')
            if not password:
                self.stderr.write(self.style.ERROR(f'Se omitió {username}: contraseña vacía.'))
                continue
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.save(update_fields=['password'])
            UserAccess.objects.update_or_create(
                user=user,
                defaults={'must_change_password': True},
            )
            self.stdout.write(self.style.SUCCESS(f'Cuenta preparada: {username}'))
