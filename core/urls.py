from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import AppLoginView, change_password, communications, contact_form, dashboard, home, jornada_api, matches_api, origins, public_home, setup_collaborators, statistics, statistics_api, tournaments, vip_matches

urlpatterns = [
    path('', home, name='home'),
    path('publico/', public_home, name='public_home'),
    path('torneos/', tournaments, name='tournaments'),
    path('partidos-vip/', vip_matches, name='vip_matches'),
    path('procedencia/', origins, name='origins'),
    path('comunicaciones/', communications, name='communications'),
    path('actualizar-contacto/', contact_form, name='contact_form'),
    path('datos/', dashboard, name='dashboard'),
    path('estadisticas/', statistics, name='statistics'),
    path('login/', AppLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='/login/'), name='logout'),
    path('cambiar-contrasena/', change_password, name='change_password'),
    path('configurar-colaboradores/', setup_collaborators, name='setup_collaborators'),
    path('api/partidos/<int:season>/<int:round_number>/', matches_api, name='matches_api'),
    path('api/jornada/<int:season>/<int:jornada>/', jornada_api, name='jornada_api'),
    path('api/estadisticas/<int:season>/<int:jornada>/', statistics_api, name='statistics_api'),
]
