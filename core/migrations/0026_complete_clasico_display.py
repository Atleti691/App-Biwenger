"""Complete only the verified 2026 VIP Clásico's missing presentation fields.

Source: https://www.laliga.com/partidazos/el-clasico (25/10/2026 match),
checked 28/10/2026: Barcelona 1-2 Real Madrid, Raphinha 61', Mbappé 41'/87'.
Do not change the three real goals, votes, penalties, or any other match.
"""
from django.db import migrations


def complete_clasico(apps, schema_editor):
    PartidoVIP = apps.get_model('core', 'PartidoVIP')
    matches = PartidoVIP.objects.using(schema_editor.connection.alias).filter(
        titulo__iexact='Vuelve el Clasico', equipo_local__iexact='Barcelona',
        equipo_visitante__iexact='Real Madrid', jornada=10, cerrado=True, goles_reales=3,
        fecha_cierre__gte='2026-10-20T00:00:00+00:00', fecha_cierre__lt='2026-10-26T00:00:00+00:00')
    for match in matches:
        updates = {}
        if not (match.resultado or '').strip():
            updates['resultado'] = '1–2'
        if not (match.goleadores or '').strip():
            updates['goleadores'] = 'Barcelona: Raphinha (61’). Real Madrid: Mbappé (41’ y 87’).'
        if updates:
            PartidoVIP.objects.using(schema_editor.connection.alias).filter(pk=match.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [('core', '0025_correopenalizacionvip')]
    operations = [migrations.RunPython(complete_clasico, migrations.RunPython.noop)]
