"""Visual QA using fictitious data; not a production export."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from core.clause_pdf import build_clause_pdf

names = ['Alex Julio', "Kabe's Team", 'Marina', 'Gabrielix de Asturin'] + [f'Manager de ejemplo {i}' for i in range(5,19)]
links = [{'source':name,'target':names[(i+1)%len(names)],'count':i%9+1,'value':1234567+i*1000} for i,name in enumerate(names)]
for filename, manager in [('mapa-clausulas-ejemplo.pdf',None), ('manager-clausulas-ejemplo.pdf',names[0])]:
    (ROOT/'tmp/pdfs'/filename).write_bytes(build_clause_pdf(links, 'Primera División', 'Datos ficticios de prueba', manager))
