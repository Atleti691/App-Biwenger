"""Generate a fictitious preview of the actual standings image; send no mail."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import django
django.setup()
from core.journey_emails import standings_png

names = ['Equipo Norte', 'Los Jugones', 'Atlético del Barrio', 'Fútbol y Amigos',
         'La Banda FC', 'Sporting del Sur', 'Real Cantera', 'Deportivo Once']
rows = [{'manager': name, 'total': total} for name, total in zip(names, [1184,1167,1152,1129,1108,1096,1071,1054])]
round_totals = dict(zip(names, [94,87,103,76,90,82,69,88]))
folder = ROOT/'output/images'
folder.mkdir(parents=True, exist_ok=True)
path = folder/'ejemplo-clasificacion-jornada.png'
path.write_bytes(standings_png('Primera División · EJEMPLO', 11, rows, round_totals))
print(path)
