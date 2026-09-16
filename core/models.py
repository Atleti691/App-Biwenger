from django.conf import settings
from django.db import models


class UserAccess(models.Model):
    ROLE_CHOICES = [
        ('viewer', 'Solo consulta'),
        ('collaborator', 'Colaborador'),
        ('admin', 'Administrador'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    division = models.CharField(max_length=80, blank=True)
    must_change_password = models.BooleanField(default=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    is_viewer = models.BooleanField(default=False)
    access_expires_at = models.DateTimeField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    editable_divisions = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.division or "Administrador"}'


class JornadaRegistro(models.Model):
    user_access = models.ForeignKey(UserAccess, on_delete=models.CASCADE)
    division = models.CharField(max_length=80, default='')
    season = models.PositiveIntegerField(default=2026)
    jornada = models.PositiveIntegerField()
    puntos_app = models.IntegerField(default=0)
    aciertos_quinielas = models.PositiveIntegerField(default=0)
    aciertos_porras = models.PositiveIntegerField(default=0)
    penalizacion_dinero_clausulas = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    penalizacion_puntos_clausulas = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    datos = models.JSONField(default=dict, blank=True)
    cerrada = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user_access', 'season', 'jornada', 'division')

    @property
    def puntos_porras_quinielas(self):
        return self.aciertos_quinielas * 5 + self.aciertos_porras * 10

    @property
    def total_jornada(self):
        return self.puntos_app + self.puntos_porras_quinielas

    @property
    def total_neto_jornada(self):
        return self.total_jornada - self.penalizacion_puntos_clausulas


class Clausula(models.Model):
    jornada = models.ForeignKey(JornadaRegistro, on_delete=models.CASCADE, related_name='clausulas')
    numero = models.PositiveSmallIntegerField()
    jugador = models.CharField(max_length=120)
    valor_dinero = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    penalizacion_dinero = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    penalizacion_puntos = models.IntegerField(default=0)


class CambioRegistro(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    division = models.CharField(max_length=80, blank=True)
    season = models.PositiveIntegerField(default=2026)
    jornada = models.PositiveIntegerField()
    accion = models.CharField(max_length=80)
    detalle = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True)


class ContactoManager(models.Model):
    division = models.CharField(max_length=80)
    manager = models.CharField(max_length=120)
    email = models.EmailField()
    provincia = models.CharField(max_length=80)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('division', 'manager')

    def __str__(self):
        return f'{self.manager} — {self.division}'


class PartidoVIP(models.Model):
    titulo = models.CharField(max_length=140)
    equipo_local = models.CharField(max_length=80)
    equipo_visitante = models.CharField(max_length=80)
    fecha_cierre = models.DateTimeField()
    goles_reales = models.PositiveSmallIntegerField(null=True, blank=True)
    cerrado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    @property
    def opcion_goles_real(self):
        if self.goles_reales is None:
            return ''
        return '3+' if self.goles_reales >= 3 else str(self.goles_reales)

    def __str__(self):
        return self.titulo


class VotoPartidoVIP(models.Model):
    POSITION_CHOICES = [('local', 'Equipo local'), ('visitante', 'Equipo visitante'), ('ninguno', 'Ninguno')]
    GOAL_CHOICES = [('0', '0 goles'), ('1', '1 gol'), ('2', '2 goles'), ('3+', '3 o más goles')]
    partido = models.ForeignKey(PartidoVIP, on_delete=models.CASCADE, related_name='votos')
    division = models.CharField(max_length=80)
    manager = models.CharField(max_length=120)
    posicionamiento = models.CharField(max_length=12, choices=POSITION_CHOICES)
    pronostico_goles = models.CharField(max_length=2, choices=GOAL_CHOICES)
    objetivo_penalizacion = models.CharField(max_length=120, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('partido', 'division', 'manager')
