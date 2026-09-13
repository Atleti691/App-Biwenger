from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0002_jornadaregistro_cerrada_jornadaregistro_datos')]
    operations = [
        migrations.AddField(model_name='jornadaregistro', name='division', field=models.CharField(default='', max_length=80)),
        migrations.AlterUniqueTogether(name='jornadaregistro', unique_together={('user_access', 'season', 'jornada', 'division')}),
        migrations.CreateModel(name='CambioRegistro', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('division', models.CharField(blank=True, max_length=80)),
            ('season', models.PositiveIntegerField(default=2026)),
            ('jornada', models.PositiveIntegerField()),
            ('accion', models.CharField(max_length=80)),
            ('detalle', models.JSONField(blank=True, default=dict)),
            ('creado', models.DateTimeField(auto_now_add=True)),
            ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
    ]
