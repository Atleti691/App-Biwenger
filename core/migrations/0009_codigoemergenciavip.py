from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_partidovip_escudo_local_partidovip_escudo_visitante'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CodigoEmergenciaVIP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('division', models.CharField(max_length=80)),
                ('manager', models.CharField(max_length=120)),
                ('codigo_hash', models.CharField(max_length=128)),
                ('caduca', models.DateTimeField()),
                ('usado', models.DateTimeField(blank=True, null=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('partido', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='codigos_emergencia', to='core.partidovip')),
            ],
            options={'ordering': ('-creado',)},
        ),
    ]
