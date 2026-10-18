"""Local visual check with fictitious data, never the production database."""
import os
import sys
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from core.models import PartidoVIP, UserAccess, VotoPartidoVIP, JornadaRegistro

call_command('migrate', verbosity=0)
admin = get_user_model().objects.create_user('preview_admin')
access = UserAccess.objects.create(user=admin, role='admin', must_change_password=False)
match = PartidoVIP.objects.create(titulo='Derbi madrileño · Ejemplo de prueba', jornada=7,
    equipo_local='Atlético de Madrid', equipo_visitante='Real Madrid',
    fecha_cierre=timezone.now()-timedelta(days=2), cerrado=True, goles_reales=3,
    resultado='2-1', goleadores='Datos ficticios para revisar el diseño')
roster = {'Primera División':[f'Manager {i}' for i in range(80)]}
VotoPartidoVIP.objects.bulk_create([VotoPartidoVIP(partido=match, division='Primera División',
    manager=f'Manager {i}', posicionamiento=('local','visitante','ninguno')[i%3], pronostico_goles='3+') for i in range(73)])
JornadaRegistro.objects.create(user_access=access, season=2026, jornada=7, division='Primera División',
    cerrada=True, datos={f'Manager {i}':{'app':str(50+i%3*5)} for i in range(80)})
client = Client()
client.force_login(admin)
folder = ROOT/'tmp/vip-preview'
folder.mkdir(parents=True,exist_ok=True)
with patch('core.views.active_league_managers', return_value=roster), patch('core.views.get_team_logo', return_value=''), patch('core.views.get_preferred_team_logo', return_value=''):
    for path, filename in [('/partidos-vip/','consulta.html'),('/gestion/partidos-vip/','gestion.html'),('/?menu=gestion','menu.html')]:
        response=client.get(path)
        assert response.status_code == 200
        (folder/filename).write_bytes(response.content)
print('Vistas de prueba generadas sin tocar datos reales.')
