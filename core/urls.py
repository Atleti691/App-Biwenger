from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import AppLoginView, change_password, dashboard, home, jornada_api, matches_api, public_home, setup_collaborators, tournaments

urlpatterns = [
    path('', home, name='home'),
    path('publico/', public_home, name='public_home'),
    path('torneos/', tournaments, name='tournaments'),
    path('datos/', dashboard, name='dashboard'),
    path('login/', AppLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='/login/'), name='logout'),
    path('cambiar-contrasena/', change_password, name='change_password'),
    path('configurar-colaboradores/', setup_collaborators, name='setup_collaborators'),
    path('api/partidos/<int:season>/<int:round_number>/', matches_api, name='matches_api'),
    path('api/jornada/<int:season>/<int:jornada>/', jornada_api, name='jornada_api'),
]
