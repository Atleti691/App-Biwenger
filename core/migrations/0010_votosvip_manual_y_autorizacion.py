from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_codigoemergenciavip'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='codigoemergenciavip',
            name='proposito',
            field=models.CharField(default='votar', max_length=20),
        ),
        migrations.AddField(
            model_name='votopartidovip',
            name='origen',
            field=models.CharField(default='usuario', max_length=20),
        ),
        migrations.AddField(
            model_name='votopartidovip',
            name='registrado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='votos_vip_registrados', to=settings.AUTH_USER_MODEL),
        ),
    ]
