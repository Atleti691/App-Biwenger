from django.db import migrations, models


def add_derby_result(apps, schema_editor):
    PartidoVIP = apps.get_model('core', 'PartidoVIP')
    for match in PartidoVIP.objects.all():
        teams = f'{match.equipo_local} {match.equipo_visitante}'.lower()
        if 'real madrid' in teams and ('atlético' in teams or 'atletico' in teams):
            match.resultado = 'Atlético de Madrid 2–1 Real Madrid'
            match.goleadores = 'Grimaldo (53’), Jonathan David (59’) y Rüdiger (89’)'
            match.save(update_fields=['resultado', 'goleadores'])


class Migration(migrations.Migration):
    dependencies = [('core', '0017_sugerencias')]
    operations = [
        migrations.AddField(model_name='partidovip', name='resultado', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='partidovip', name='goleadores', field=models.TextField(blank=True)),
        migrations.RunPython(add_derby_result, migrations.RunPython.noop),
    ]
