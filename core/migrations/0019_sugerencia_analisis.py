from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0018_partidovip_resultado_goleadores')]

    operations = [
        migrations.AddField(model_name='sugerencia', name='analisis', field=models.TextField(blank=True)),
        migrations.AddField(model_name='sugerencia', name='prioridad_analisis', field=models.CharField(blank=True, max_length=12)),
        migrations.AddField(model_name='sugerencia', name='analizada', field=models.DateTimeField(blank=True, null=True)),
    ]
