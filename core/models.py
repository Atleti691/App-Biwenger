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


class ManagerLiga(models.Model):
    season = models.PositiveIntegerField(default=2026)
    division = models.CharField(max_length=80)
    manager = models.CharField(max_length=120)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('season', 'division', 'manager')
        ordering = ('division', 'manager')

    def __str__(self):
        return f'{self.manager} — {self.division} ({self.season})'


class PartidoVIP(models.Model):
    titulo = models.CharField(max_length=140)
    jornada = models.PositiveSmallIntegerField(null=True, blank=True)
    equipo_local = models.CharField(max_length=80)
    equipo_visitante = models.CharField(max_length=80)
    escudo_local = models.URLField(blank=True)
    escudo_visitante = models.URLField(blank=True)
    fecha_cierre = models.DateTimeField()
    goles_reales = models.PositiveSmallIntegerField(null=True, blank=True)
    resultado = models.CharField(max_length=80, blank=True)
    goleadores = models.TextField(blank=True)
    cerrado = models.BooleanField(default=False)
    notificaciones_ganadores = models.JSONField(default=list, blank=True)
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
    penalizaciones_objetivo = models.JSONField(default=dict, blank=True)
    origen = models.CharField(max_length=20, default='usuario')
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='votos_vip_registrados')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('partido', 'division', 'manager')


class CodigoEmergenciaVIP(models.Model):
    partido = models.ForeignKey(PartidoVIP, on_delete=models.CASCADE, related_name='codigos_emergencia')
    division = models.CharField(max_length=80)
    manager = models.CharField(max_length=120)
    codigo_hash = models.CharField(max_length=128)
    proposito = models.CharField(max_length=20, default='votar')
    caduca = models.DateTimeField()
    usado = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-creado',)

    def __str__(self):
        return f'{self.manager} — {self.partido}'


class Sugerencia(models.Model):
    CATEGORY_CHOICES = [('datos', 'Introducción de datos'), ('estadisticas', 'Estadísticas'), ('vip', 'Partidos VIP'), ('torneos', 'Torneos'), ('usuarios', 'Usuarios y accesos'), ('otra', 'Otra mejora')]
    STATUS_CHOICES = [('nueva', 'Nueva'), ('estudio', 'En estudio'), ('aceptada', 'Aceptada'), ('desarrollo', 'En desarrollo'), ('realizada', 'Realizada'), ('descartada', 'Descartada')]
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sugerencias')
    titulo = models.CharField(max_length=140)
    descripcion = models.TextField()
    categoria = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='otra')
    estado = models.CharField(max_length=20, choices=STATUS_CHOICES, default='nueva')
    anonima = models.BooleanField(default=False)
    respuesta = models.TextField(blank=True)
    analisis = models.TextField(blank=True)
    prioridad_analisis = models.CharField(max_length=12, blank=True)
    analizada = models.DateTimeField(null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-creada',)


class VotoSugerencia(models.Model):
    sugerencia = models.ForeignKey(Sugerencia, on_delete=models.CASCADE, related_name='votos')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sugerencia', 'usuario')
