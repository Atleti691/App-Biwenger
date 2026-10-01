from django.contrib.auth.views import LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetCompleteView
from django.urls import path, reverse_lazy
from .password_recovery import LeaguePasswordResetConfirmView, LeaguePasswordResetForm
from .views import AppLoginView, administration_log, assistant_guide, change_password, communications, contact_form, dashboard, delete_suggestion, home, jornada_api, journey_summary, manage_managers, matches_api, origins, public_home, setup_collaborators, statistics, statistics_api, suggestions, tournaments, vip_matches, vip_penalty_choice, vip_statistics, vip_vote

urlpatterns = [
    path('', home, name='home'),
    path('publico/', public_home, name='public_home'),
    path('torneos/', tournaments, name='tournaments'),
    path('partidos-vip/', vip_matches, name='vip_matches'),
    path('partidos-vip/votar/<int:partido_id>/', vip_vote, name='vip_vote'),
    path('partidos-vip/penalizacion/<str:token>/', vip_penalty_choice, name='vip_penalty_choice'),
    path('procedencia/', origins, name='origins'),
    path('comunicaciones/', communications, name='communications'),
    path('actualizar-contacto/', contact_form, name='contact_form'),
    path('datos/', dashboard, name='dashboard'),
    path('resumen-jornadas/', journey_summary, name='journey_summary'),
    path('estadisticas/', statistics, name='statistics'),
    path('estadisticas/partidos-vip/', vip_statistics, name='vip_statistics'),
    path('login/', AppLoginView.as_view(), name='login'),
    path('recuperar-contrasena/', PasswordResetView.as_view(form_class=LeaguePasswordResetForm, template_name='password_reset_form.html', email_template_name='password_reset_email.txt', subject_template_name='password_reset_subject.txt', success_url=reverse_lazy('password_reset_done')), name='password_reset'),
    path('recuperar-contrasena/enviado/', PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('recuperar-contrasena/completado/', PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('recuperar-contrasena/<uidb64>/<token>/', LeaguePasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('logout/', LogoutView.as_view(next_page='/login/'), name='logout'),
    path('cambiar-contrasena/', change_password, name='change_password'),
    path('configurar-colaboradores/', setup_collaborators, name='setup_collaborators'),
    path('registro-administracion/', administration_log, name='administration_log'),
    path('gestionar-managers/', manage_managers, name='manage_managers'),
    path('sugerencias/', suggestions, name='suggestions'),
    path('sugerencias/<int:suggestion_id>/eliminar/', delete_suggestion, name='delete_suggestion'),
    path('asistente/', assistant_guide, name='assistant_guide'),
    path('api/partidos/<int:season>/<int:round_number>/', matches_api, name='matches_api'),
    path('api/jornada/<int:season>/<int:jornada>/', jornada_api, name='jornada_api'),
    path('api/estadisticas/<int:season>/<int:jornada>/', statistics_api, name='statistics_api'),
]
