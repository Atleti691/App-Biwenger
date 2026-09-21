from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0014_liberar_reparto_baetulo')]
    operations = [
        migrations.AddField(
            model_name='partidovip',
            name='notificaciones_ganadores',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
