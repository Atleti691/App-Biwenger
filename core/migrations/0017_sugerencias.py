from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0016_managerliga'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Sugerencia', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('titulo', models.CharField(max_length=140)), ('descripcion', models.TextField()),
            ('categoria', models.CharField(choices=[('datos','Introducción de datos'),('estadisticas','Estadísticas'),('vip','Partidos VIP'),('torneos','Torneos'),('usuarios','Usuarios y accesos'),('otra','Otra mejora')], default='otra', max_length=20)),
            ('estado', models.CharField(choices=[('nueva','Nueva'),('estudio','En estudio'),('aceptada','Aceptada'),('desarrollo','En desarrollo'),('realizada','Realizada'),('descartada','Descartada')], default='nueva', max_length=20)),
            ('anonima', models.BooleanField(default=False)), ('respuesta', models.TextField(blank=True)),
            ('creada', models.DateTimeField(auto_now_add=True)), ('actualizada', models.DateTimeField(auto_now=True)),
            ('autor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sugerencias', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ('-creada',)}),
        migrations.CreateModel(name='VotoSugerencia', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('creado', models.DateTimeField(auto_now_add=True)),
            ('sugerencia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votos', to='core.sugerencia')),
            ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ], options={'unique_together': {('sugerencia', 'usuario')}}),
    ]
