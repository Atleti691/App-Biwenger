import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0024_retire_patontografos'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='CorreoPenalizacionVIP', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('referencia', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        ('email', models.EmailField(blank=True, max_length=254)),
        ('tipo', models.CharField(default='premio', max_length=24)),
        ('estado', models.CharField(default='preparando', max_length=24, choices=[
            ('preparando', 'Preparando envío'), ('sin_correo', 'Sin correo registrado'),
            ('error', 'Error de envío'), ('enviado', 'Enviado · entrega sin confirmar'),
            ('entregado', 'Entrega confirmada por Brevo'), ('rechazado', 'Rechazado o bloqueado'),
            ('aplazado', 'Entrega aplazada por Brevo')])),
        ('creado', models.DateTimeField(auto_now_add=True)),
        ('evento_fecha', models.DateTimeField(blank=True, null=True)),
        ('detalle', models.CharField(blank=True, max_length=300)),
        ('solicitado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ('voto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correos_penalizacion', to='core.votopartidovip')),
    ]), migrations.AddConstraint(model_name='correopenalizacionvip',
        constraint=models.UniqueConstraint(fields=('voto',), name='vip_last_day_once',
            condition=models.Q(tipo='ultimo_dia', estado__in=['preparando', 'enviado', 'entregado', 'aplazado'])))]
