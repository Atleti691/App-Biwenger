from datetime import timedelta
import secrets
import unicodedata
import logging

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import FirstPasswordChangeForm, LoginForm
from .models import CambioRegistro, CodigoEmergenciaVIP, ContactoManager, JornadaRegistro, PartidoVIP, UserAccess, VotoPartidoVIP
from .services.openligadb import get_matches, get_preferred_team_logo, get_team_logo

logger = logging.getLogger(__name__)


def send_vip_penalty_links(request, partido, votes):
    contacts = {(c.division, c.manager): c.email.strip() for c in ContactoManager.objects.exclude(email='')}
    connection = get_connection(fail_silently=False)
    messages = []
    for vote in votes:
        email = contacts.get((vote.division, vote.manager))
        if not email:
            continue
        token = signing.dumps({'partido': partido.id, 'division': vote.division, 'manager': vote.manager}, salt='vip-penalty')
        url = request.build_absolute_uri(f'/partidos-vip/penalizacion/{token}/')
        messages.append(EmailMessage(subject=f'Premio por acertar los goles — {partido.titulo}', body=(f'Hola {vote.manager}.\n\nHas acertado el número de goles de {partido.titulo}. Debes repartir exactamente 50 puntos de penalización entre uno o varios managers de tu división:\n{url}\n\nSolo podrás realizar esta elección una vez.'), to=[email], connection=connection))
    return connection.send_messages(messages) if messages else 0


def vip_adjustments_for_journey(jornada):
    adjustments = {}
    records = {}
    for record in JornadaRegistro.objects.filter(jornada=jornada).order_by('division', '-updated_at'):
        records.setdefault(record.division, record)
    base_points = {}
    for division, record in records.items():
        if not record.cerrada:
            continue
        for manager, row in (record.datos or {}).items():
            base_points[(division, manager)] = int(row.get('app') or 0) + int(row.get('q') or 0) * 5 + int(row.get('p') or 0) * 10 - int(row.get('penalty') or 0)
    for partido in PartidoVIP.objects.filter(jornada=jornada, cerrado=True).prefetch_related('votos'):
        votes = list(partido.votos.all())
        for division in LEAGUE_MANAGERS:
            division_votes = [vote for vote in votes if vote.division == division]
            if records.get(division) and records[division].cerrada:
                groups = {'local': [], 'visitante': []}
                for vote in division_votes:
                    if vote.posicionamiento in groups and (division, vote.manager) in base_points:
                        groups[vote.posicionamiento].append(base_points[(division, vote.manager)])
                averages = {key: (sum(values) / len(values) if values else None) for key, values in groups.items()}
                winner = ''
                if averages['local'] is not None and averages['visitante'] is not None and averages['local'] != averages['visitante']:
                    winner = 'local' if averages['local'] > averages['visitante'] else 'visitante'
                for vote in division_votes:
                    key = (division, vote.manager)
                    adjustments[key] = adjustments.get(key, 0) - 10
                    if winner and vote.posicionamiento == winner:
                        adjustments[key] += 100
            for vote in division_votes:
                penalties = vote.penalizaciones_objetivo or ({vote.objetivo_penalizacion: 50} if vote.objetivo_penalizacion else {})
                for target, points in penalties.items():
                    target_key = (division, target)
                    adjustments[target_key] = adjustments.get(target_key, 0) - int(points or 0)
    return adjustments


def vip_breakdown_for_journey(jornada, division):
    """Return the two visible VIP concepts for one division and journey."""
    partidos = PartidoVIP.objects.filter(jornada=jornada).prefetch_related('votos')
    has_vip = partidos.exists()
    positioning = {manager: 0 for manager in LEAGUE_MANAGERS.get(division, [])}
    penalties = {manager: 0 for manager in LEAGUE_MANAGERS.get(division, [])}
    if not has_vip:
        return False, positioning, penalties
    record = JornadaRegistro.objects.filter(jornada=jornada, division=division).order_by('-updated_at').first()
    division_closed = bool(record and record.cerrada)
    base_points = {}
    if division_closed:
        for manager, row in (record.datos or {}).items():
            base_points[manager] = int(row.get('app') or 0) + int(row.get('q') or 0) * 5 + int(row.get('p') or 0) * 10 - int(row.get('penalty') or 0)
    for partido in partidos.filter(cerrado=True):
        votes = list(partido.votos.filter(division=division))
        groups = {'local': [], 'visitante': []}
        if division_closed:
            for vote in votes:
                if vote.posicionamiento in groups and vote.manager in base_points:
                    groups[vote.posicionamiento].append(base_points[vote.manager])
        averages = {key: (sum(values) / len(values) if values else None) for key, values in groups.items()}
        winner = ''
        if averages['local'] is not None and averages['visitante'] is not None and averages['local'] != averages['visitante']:
            winner = 'local' if averages['local'] > averages['visitante'] else 'visitante'
        for vote in votes:
            if division_closed:
                positioning[vote.manager] = positioning.get(vote.manager, 0) - 10
                if winner and vote.posicionamiento == winner:
                    positioning[vote.manager] += 100
            distributed = vote.penalizaciones_objetivo or ({vote.objetivo_penalizacion: 50} if vote.objetivo_penalizacion else {})
            for target, points in distributed.items():
                penalties[target] = penalties.get(target, 0) - int(points or 0)
    return True, positioning, penalties

EDIT_DIVISIONS = {
    'Atleti69': {'*'},
    'Kabes Team': {'Primera División', 'Liga Moeve'},
    'LLull Team': {'Segunda División'},
    'Reventao': {'Primera RFEF'},
    'Carbayon': {'Segunda RFEF'},
}


def fixed_edit_divisions(username):
    """Return protected staff divisions without depending on username casing."""
    folded_username = (username or '').casefold()
    for fixed_username, divisions in EDIT_DIVISIONS.items():
        if fixed_username.casefold() == folded_username:
            return divisions
    return set()

LEAGUE_MANAGERS = {
    'Primera Divisi\u00f3n': ['AlexJulio','Rexza','C.D.F. Arrieritos','Gestafa FC','Golden Ball','Ivanetti',"Kabe's Team",'Maceda','Mouki','Munera City','Raul C','Real JR','I\u00f1igoool!!!!','Reventao','Tuercebotas','Llull Team','Pablo Cuevas','Joselillo81'],
    'Segunda Divisi\u00f3n': ['Marina','Kataki Villenero','Carbayon','At. Aviacion','Vendy','Goyo','Rocky Team','Ruben 1903ATM','Jackobo','Baetulo','FC Almog\u00e1vers','Re Creativo Igualadino','Rapido de Bouzas','Gasteiz United','eMCasa','Gabrielix de Asturin','Adrianpt260','SpartanAgain'],
    'Primera RFEF': ['Estefan\u00eda','Guerreros F.C','Pcotop Team','El Cabo','Checo21','C.D. Covadonga','Patontografos F.C','CD Cayon','Resalso','Beagar13','Gsgg Team','Manuymarian',"Minuto 94'",'JAM F.C.','Litoscaboalles','Atleti69','Maicame'],
    'Segunda RFEF': ['Semela','Soar FC','UnaiRZ','Izan Navarro','JaviArsenal','Jose Mourinho','Mu\u00f1eko','Danilo77','Alex SC','K87','EmiGeta','A.A. Ponte Preta','Atletico Zaragoza','Peluso F.C.','Emilio Ramos','Sevi-21','Esta NFL No la Entiendo','Deckers'],
    'Liga Moeve': ['Titanes65','Antbariba','El Macho','Palacios FC','Real Oviedo','OskitarTeam','Jopehe95','Schalke Te meto','Caimans','Shaiel Afonso Rodriguez','RBN147','Ivan Diaz'],
}


def restore_fixed_staff_access(user, access):
    """Keep the administrator and original collaborators out of viewer mode."""
    fixed_staff = {username.casefold(): (username, divisions) for username, divisions in EDIT_DIVISIONS.items()}
    fixed_entry = fixed_staff.get(user.username.casefold())
    if user.username.casefold() == 'atleti69':
        expected_role = 'admin'
        expected_divisions = []
    elif fixed_entry:
        expected_role = 'collaborator'
        expected_divisions = sorted(fixed_entry[1] - {'*'})
    else:
        return access
    changed_fields = []
    if access.role != expected_role:
        access.role = expected_role
        changed_fields.append('role')
    if access.is_viewer:
        access.is_viewer = False
        changed_fields.append('is_viewer')
    if access.editable_divisions != expected_divisions:
        access.editable_divisions = expected_divisions
        changed_fields.append('editable_divisions')
    if changed_fields:
        access.save(update_fields=changed_fields)
    return access


def restore_all_fixed_staff_access():
    for username in EDIT_DIVISIONS:
        user = get_user_model().objects.filter(username__iexact=username).first()
        if user:
            access, _ = UserAccess.objects.get_or_create(user=user)
            restore_fixed_staff_access(user, access)


@login_required
def home(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    if access.access_expires_at and access.access_expires_at <= timezone.now():
        logout(request)
        return redirect('/login/?expired=1')
    if access.must_change_password and request.GET.get('skip') != '1':
        return redirect('/cambiar-contrasena/')
    return render(request, 'home.html', {'is_viewer': access.role == 'viewer'})


def public_home(request):
    return render(request, 'public_home.html')


def contact_form(request):
    message = ''
    selected_division = request.POST.get('division', '')
    if request.method == 'POST':
        manager = request.POST.get('manager', '').strip()
        email = request.POST.get('email', '').strip()
        provincia = request.POST.get('provincia', '').strip()
        if selected_division in LEAGUE_MANAGERS and manager in LEAGUE_MANAGERS[selected_division] and email and provincia:
            ContactoManager.objects.update_or_create(division=selected_division, manager=manager, defaults={'email': email, 'provincia': provincia})
            message = 'Datos guardados correctamente. Muchas gracias.'
        else:
            message = 'Revisa la división, el manager, el correo y la provincia.'
    return render(request, 'contact_form.html', {'league_managers': LEAGUE_MANAGERS, 'message': message, 'selected_division': selected_division})


@login_required
def communications(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    if request.user.username.casefold() != 'atleti69' and access.role != 'admin':
        return redirect('/')
    restore_all_fixed_staff_access()
    message = ''
    access_action_result = request.session.pop('access_action_result', None)
    if request.method == 'POST' and request.POST.get('action') == 'reset_viewer_access':
        contact = get_object_or_404(ContactoManager, pk=request.POST.get('contact_id'))
        user = get_user_model().objects.filter(username__iexact=contact.manager).first()
        if not user:
            message = f'Todavía no existe una cuenta para {contact.manager}.'
        else:
            account, _ = UserAccess.objects.get_or_create(user=user)
            account = restore_fixed_staff_access(user, account)
            if account.role != 'viewer' or user.username.casefold() in {name.casefold() for name in EDIT_DIVISIONS}:
                message = 'No se ha modificado la contraseña: esta cuenta pertenece a un administrador o colaborador protegido.'
            elif not contact.email.strip():
                message = f'{contact.manager} no tiene correo registrado.'
            else:
                alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
                initial_password = ''.join(secrets.choice(alphabet) for _ in range(10))
                previous_password = user.password
                previous_email = user.email
                previous_must_change = account.must_change_password
                user.set_password(initial_password)
                user.email = contact.email.strip()
                user.save(update_fields=['password', 'email'])
                account.must_change_password = True
                account.save(update_fields=['must_change_password'])
                login_url = request.build_absolute_uri('/login/')
                try:
                    sent = EmailMessage(
                        subject='Nueva contraseña temporal — Liga Amigos XI',
                        body=(f'Hola {contact.manager}.\n\nSe ha generado una nueva contraseña temporal para tu cuenta.\n\n'
                              f'Usuario: {user.username}\nContraseña temporal: {initial_password}\nAcceso: {login_url}\n\n'
                              'La contraseña anterior ya no funciona. Al entrar tendrás que elegir una contraseña nueva.'),
                        to=[contact.email.strip()],
                    ).send(fail_silently=False)
                except Exception:
                    logger.exception('No se pudo reenviar el acceso de consulta a %s', contact.manager)
                    sent = 0
                if not sent:
                    user.password = previous_password
                    user.email = previous_email
                    user.save(update_fields=['password', 'email'])
                    account.must_change_password = previous_must_change
                    account.save(update_fields=['must_change_password'])
                CambioRegistro.objects.create(usuario=request.user, jornada=0, accion='regenerar acceso de consulta', detalle={'manager': contact.manager, 'correo_enviado': bool(sent)})
                message = (f'Nueva contraseña enviada a {contact.manager}.' if sent else
                           f'No se pudo enviar el correo a {contact.manager}; se ha conservado su contraseña anterior.')
        access_action_result = {
            'contact_id': contact.id,
            'ok': message.startswith('Nueva contraseña enviada'),
            'message': message,
            'temporary_password': initial_password if 'initial_password' in locals() and sent else '',
        }
        request.session['access_action_result'] = access_action_result
        target_anchor = 'temporary-password-card' if access_action_result['temporary_password'] else f'access-row-{contact.id}'
        return redirect(f'/comunicaciones/#{target_anchor}')
    elif request.method == 'POST' and request.POST.get('action') == 'create_viewer_one':
        contact = get_object_or_404(ContactoManager, pk=request.POST.get('contact_id'))
        if not contact.email.strip():
            return JsonResponse({'ok': False, 'manager': contact.manager, 'error': 'No tiene correo registrado'}, status=400)
        user = get_user_model().objects.filter(username__iexact=contact.manager).first()
        if user:
            account, account_created = UserAccess.objects.get_or_create(user=user)
            restore_fixed_staff_access(user, account)
            if not account_created:
                return JsonResponse({'ok': True, 'manager': contact.manager, 'status': 'existing', 'email_sent': False})
        else:
            alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
            initial_password = ''.join(secrets.choice(alphabet) for _ in range(10))
            user = get_user_model().objects.create_user(username=contact.manager, email=contact.email, password=initial_password)
            UserAccess.objects.create(user=user, must_change_password=True, is_viewer=True, role='viewer', editable_divisions=[])
            login_url = request.build_absolute_uri('/login/')
            try:
                sent = EmailMessage(
                    subject='Acceso de consulta — Liga Amigos XI',
                    body=(f'Hola {contact.manager}.\n\nYa tienes acceso de consulta a Liga Amigos XI.\n\n'
                          f'Usuario: {contact.manager}\nContraseña inicial: {initial_password}\nAcceso: {login_url}\n\n'
                          'Al entrar tendrás que cambiar la contraseña. Tu perfil solo permite consultar estadísticas y el mapa de procedencia.'),
                    to=[contact.email],
                ).send(fail_silently=False)
            except Exception:
                logger.exception('No se pudo enviar el acceso de consulta a %s', contact.manager)
                sent = 0
            CambioRegistro.objects.create(usuario=request.user, jornada=0, accion='crear acceso de consulta', detalle={'manager': contact.manager, 'correo_enviado': bool(sent)})
            return JsonResponse({'ok': True, 'manager': contact.manager, 'status': 'created', 'email_sent': bool(sent)})
        return JsonResponse({'ok': True, 'manager': contact.manager, 'status': 'existing', 'email_sent': False})
    elif request.method == 'POST' and request.POST.get('action') == 'create_viewers':
        created_count = sent_count = skipped_count = 0
        login_url = request.build_absolute_uri('/login/')
        access_messages = []
        for contact in ContactoManager.objects.exclude(email='').order_by('division', 'manager'):
            existing_user = get_user_model().objects.filter(username__iexact=contact.manager).first()
            if existing_user:
                existing_access, _ = UserAccess.objects.get_or_create(user=existing_user)
                restore_fixed_staff_access(existing_user, existing_access)
                skipped_count += 1
                continue
            alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
            initial_password = ''.join(secrets.choice(alphabet) for _ in range(10))
            user = get_user_model().objects.create_user(username=contact.manager, email=contact.email, password=initial_password)
            UserAccess.objects.create(user=user, must_change_password=True, is_viewer=True, role='viewer', editable_divisions=[])
            created_count += 1
            access_messages.append(EmailMessage(
                subject='Acceso de consulta — Liga Amigos XI',
                body=(f'Hola {contact.manager}.\n\nYa tienes acceso de consulta a Liga Amigos XI.\n\n'
                      f'Usuario: {contact.manager}\nContraseña inicial: {initial_password}\nAcceso: {login_url}\n\n'
                      'Al entrar tendrás que cambiar la contraseña. Tu perfil solo permite consultar estadísticas y el mapa de procedencia.'),
                to=[contact.email],
            ))
        if access_messages:
            try:
                sent_count = get_connection(fail_silently=False).send_messages(access_messages) or 0
            except Exception:
                logger.exception('No se pudieron enviar los accesos de consulta')
        CambioRegistro.objects.create(usuario=request.user, jornada=0, accion='crear accesos de consulta', detalle={'creados': created_count, 'correos_enviados': sent_count, 'existentes': skipped_count})
        message = f'Se crearon {created_count} cuentas de consulta y se enviaron {sent_count} correos.'
        if skipped_count:
            message += f' Se conservaron {skipped_count} cuentas que ya existían.'
        if sent_count < created_count:
            message += f' No se pudieron enviar {created_count - sent_count} correos; puedes asignarles una contraseña nueva desde Gestionar colaboradores.'
    elif request.method == 'POST':
        contact = get_object_or_404(ContactoManager, pk=request.POST.get('contact_id'))
        email = request.POST.get('email', '').strip()
        provincia = request.POST.get('provincia', '').strip()
        if email and provincia:
            contact.email = email
            contact.provincia = provincia
            contact.save(update_fields=['email', 'provincia', 'actualizado'])
            message = f'Datos de {contact.manager} actualizados correctamente.'
        else:
            message = 'El correo y la provincia son obligatorios.'
    contacts = {(item.division, item.manager): item for item in ContactoManager.objects.all()}
    app_accounts = {account.user.username.casefold(): account for account in UserAccess.objects.select_related('user')}
    rows = [{'division': division, 'manager': manager, 'contact': contacts.get((division, manager)), 'app_account': app_accounts.get(manager.casefold())} for division, managers in LEAGUE_MANAGERS.items() for manager in managers]
    completed = sum(1 for row in rows if row['contact'] and row['contact'].email.strip())
    total = len(rows)
    completed_percentage = round(completed * 100 / total) if total else 0
    pending_accounts = [{'id': row['contact'].id, 'manager': row['manager']} for row in rows if row['contact'] and not row['app_account']]
    share_url = request.build_absolute_uri('/actualizar-contacto/')
    return render(request, 'communications.html', {'rows': rows, 'share_url': share_url, 'completed': completed, 'total': total, 'completed_percentage': completed_percentage, 'pending_accounts': pending_accounts, 'message': message, 'access_action_result': access_action_result})


@login_required
def vip_matches(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    if access.role == 'viewer':
        return redirect('/')
    is_admin = request.user.username.casefold() == 'atleti69' or access.role == 'admin'
    can_create_vip = is_admin or access.role == 'collaborator'
    can_follow_vip = can_create_vip
    message = ''
    emergency_code_info = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create' and can_create_vip:
            try:
                local = request.POST.get('equipo_local', '').strip()
                visitante = request.POST.get('equipo_visitante', '').strip()
                PartidoVIP.objects.create(
                    titulo=request.POST.get('titulo', '').strip(),
                    jornada=max(1, min(38, int(request.POST['jornada']))),
                    equipo_local=local,
                    equipo_visitante=visitante,
                    escudo_local=request.POST.get('escudo_local', '').strip() or get_team_logo(local),
                    escudo_visitante=request.POST.get('escudo_visitante', '').strip() or get_team_logo(visitante),
                    fecha_cierre=timezone.make_aware(__import__('datetime').datetime.fromisoformat(request.POST['fecha_cierre'])),
                )
                message = 'Partido VIP creado.'
            except (ValueError, KeyError):
                message = 'Revisa los datos y la fecha del partido.'
        elif action == 'manual_vote' and is_admin:
            partido = get_object_or_404(PartidoVIP, pk=request.POST.get('partido_id'))
            division = request.POST.get('division', '')
            manager = request.POST.get('manager', '')
            posicionamiento = request.POST.get('posicionamiento', '')
            pronostico = request.POST.get('pronostico_goles', '')
            existing = partido.votos.filter(division=division, manager=manager).first()
            voting_finished = partido.cerrado or timezone.now() > partido.fecha_cierre
            valid_identity = manager in LEAGUE_MANAGERS.get(division, [])
            valid_choices = posicionamiento in dict(VotoPartidoVIP.POSITION_CHOICES) and pronostico in dict(VotoPartidoVIP.GOAL_CHOICES)
            if not voting_finished:
                message = 'El voto manual solo se puede registrar cuando haya terminado la votación.'
            elif existing:
                message = f'{manager} ya votó. Una votación cerrada no se puede modificar.'
            elif not valid_identity or not valid_choices:
                message = 'Revisa el manager y las opciones del voto manual.'
            else:
                VotoPartidoVIP.objects.create(partido=partido, division=division, manager=manager, posicionamiento=posicionamiento, pronostico_goles=pronostico, origen='manual', registrado_por=request.user)
                CambioRegistro.objects.create(usuario=request.user, division=division, jornada=0, accion='registrar voto VIP manual', detalle={'partido': partido.id, 'manager': manager, 'posicionamiento': posicionamiento, 'pronostico_goles': pronostico})
                message = f'Voto de {manager} guardado manualmente.'
        elif action == 'close' and is_admin:
            partido = get_object_or_404(PartidoVIP, pk=request.POST.get('partido_id'))
            partido.goles_reales = max(0, int(request.POST.get('goles_reales', 0)))
            partido.cerrado = True
            partido.save(update_fields=['goles_reales', 'cerrado'])
            winners = list(partido.votos.filter(pronostico_goles=partido.opcion_goles_real, objetivo_penalizacion='', penalizaciones_objetivo={}))
            try:
                sent = send_vip_penalty_links(request, partido, winners)
                message = f'Partido cerrado. Hay {len(winners)} acertantes y se enviaron {sent} correos para elegir la penalización.'
            except Exception:
                logger.exception('No se pudieron enviar los premios VIP de %s', partido.titulo)
                message = f'Partido cerrado. Hay {len(winners)} acertantes, pero no se pudieron enviar sus correos.'
        elif action == 'remind_penalty' and is_admin:
            partido = get_object_or_404(PartidoVIP, pk=request.POST.get('partido_id'), cerrado=True)
            winners = list(partido.votos.filter(pronostico_goles=partido.opcion_goles_real, objetivo_penalizacion='', penalizaciones_objetivo={}))
            try:
                sent = send_vip_penalty_links(request, partido, winners)
                message = f'Recordatorio enviado a {sent} de {len(winners)} acertantes pendientes.'
            except Exception:
                logger.exception('No se pudieron recordar los premios VIP de %s', partido.titulo)
                message = 'No se pudieron enviar los recordatorios a los acertantes.'
        elif action == 'remind' and is_admin:
            partido = get_object_or_404(PartidoVIP, pk=request.POST.get('partido_id'))
            voted = set(partido.votos.values_list('division', 'manager'))
            pending_contacts = [c for c in ContactoManager.objects.exclude(email='') if (c.division, c.manager) not in voted]
            recipients = list({contact.email.strip().lower(): contact.email.strip() for contact in pending_contacts}.values())
            if recipients:
                try:
                    connection = get_connection(fail_silently=False)
                    vote_url = request.build_absolute_uri(f'/partidos-vip/votar/{partido.id}/')
                    messages = [EmailMessage(subject=f'Recordatorio — {partido.titulo}', body=f'Aún no has votado en {partido.titulo}. Participa aquí: {vote_url}', to=[recipient], connection=connection) for recipient in recipients]
                    sent_count = connection.send_messages(messages)
                except Exception:
                    logger.exception('No se pudo enviar el recordatorio VIP de %s', partido.titulo)
                    sent_count = 0
                failed_count = len(recipients) - sent_count
                if sent_count and not failed_count:
                    message = f'Recordatorio enviado individualmente a {sent_count} usuarios pendientes.'
                elif sent_count:
                    message = f'Se enviaron {sent_count} recordatorios y fallaron {failed_count}. Revisa Brevo y los registros de Render.'
                else:
                    message = 'No se pudo enviar el recordatorio. Revisa los registros de Render y vuelve a intentarlo.'
            else:
                message = 'No hay usuarios pendientes con correo registrado.'
        elif action == 'emergency_code' and is_admin:
            partido = get_object_or_404(PartidoVIP, pk=request.POST.get('partido_id'), cerrado=False)
            division = request.POST.get('division', '')
            manager = request.POST.get('manager', '')
            if timezone.now() > partido.fecha_cierre:
                message = 'La votación ya ha terminado. Utiliza la opción de introducir voto manual para quienes no hayan votado.'
            elif manager not in LEAGUE_MANAGERS.get(division, []):
                message = 'No se ha podido identificar al manager seleccionado.'
            elif partido.votos.filter(division=division, manager=manager).exists():
                message = f'{manager} ya ha votado en este partido.'
            else:
                CodigoEmergenciaVIP.objects.filter(
                    partido=partido, division=division, manager=manager, proposito='votar', usado__isnull=True
                ).update(caduca=timezone.now())
                emergency_code = f'{secrets.randbelow(1000000):06d}'
                CodigoEmergenciaVIP.objects.create(
                    partido=partido,
                    division=division,
                    manager=manager,
                    codigo_hash=make_password(emergency_code),
                    proposito='votar',
                    caduca=timezone.now() + timedelta(minutes=15),
                    creado_por=request.user,
                )
                emergency_code_info = {
                    'partido_id': partido.id,
                    'division': division,
                    'manager': manager,
                    'code': emergency_code,
                }
                message = f'CÓDIGO DE EMERGENCIA · {manager} · {division}: {emergency_code} · Caduca en 15 minutos y solo puede usarse una vez.'
    partidos = list(PartidoVIP.objects.prefetch_related('votos').order_by('-creado'))
    for partido in partidos:
        manager_points = {}
        registros_jornada = JornadaRegistro.objects.filter(jornada=partido.jornada) if partido.jornada else JornadaRegistro.objects.none()
        for registro in registros_jornada:
            for manager, row in (registro.datos or {}).items():
                total = int(row.get('app') or 0) + int(row.get('q') or 0) * 5 + int(row.get('p') or 0) * 10 - int(row.get('penalty') or 0)
                manager_points[(registro.division, manager)] = total
        partido.puntos_jornada_disponibles = bool(partido.jornada) and all(
            registros_jornada.filter(division=division, cerrada=True).exists() for division in LEAGUE_MANAGERS
        )
        logo_fields = []
        preferred_local = get_preferred_team_logo(partido.equipo_local)
        preferred_visitante = get_preferred_team_logo(partido.equipo_visitante)
        if preferred_local and partido.escudo_local != preferred_local:
            partido.escudo_local = preferred_local
            logo_fields.append('escudo_local')
        elif not partido.escudo_local:
            partido.escudo_local = get_team_logo(partido.equipo_local)
            logo_fields.append('escudo_local')
        if preferred_visitante and partido.escudo_visitante != preferred_visitante:
            partido.escudo_visitante = preferred_visitante
            logo_fields.append('escudo_visitante')
        elif not partido.escudo_visitante:
            partido.escudo_visitante = get_team_logo(partido.equipo_visitante)
            logo_fields.append('escudo_visitante')
        if logo_fields and (partido.escudo_local or partido.escudo_visitante):
            partido.save(update_fields=logo_fields)
        partido.vote_url = request.build_absolute_uri(f'/partidos-vip/votar/{partido.id}/')
        partido.votacion_finalizada = partido.cerrado or timezone.now() > partido.fecha_cierre
        partido.participantes = partido.votos.count()
        if can_follow_vip:
            voted_by_division = {}
            for vote in partido.votos.all():
                voted_by_division.setdefault(vote.division, {})[vote.manager] = vote
            partido.estado_divisiones = [
                {
                    'division': division,
                    'votados': [voted_by_division.get(division, {}).get(manager) for manager in managers if manager in voted_by_division.get(division, {})],
                    'pendientes': [manager for manager in managers if manager not in voted_by_division.get(division, {})],
                    'total': len(managers),
                    'porcentaje': round(len(voted_by_division.get(division, {})) * 100 / len(managers)) if managers else 0,
                }
                for division, managers in LEAGUE_MANAGERS.items()
            ]
        groups = {'local': [], 'visitante': []}
        for vote in partido.votos.all():
            if partido.puntos_jornada_disponibles and vote.posicionamiento in groups and (vote.division, vote.manager) in manager_points:
                groups[vote.posicionamiento].append(manager_points.get((vote.division, vote.manager), 0))
        partido.media_local = round(sum(groups['local']) / len(groups['local']), 2) if groups['local'] else None
        partido.media_visitante = round(sum(groups['visitante']) / len(groups['visitante']), 2) if groups['visitante'] else None
        partido.ganador_posicionamiento = ''
        if partido.media_local is not None and partido.media_visitante is not None and partido.media_local != partido.media_visitante:
            partido.ganador_posicionamiento = 'local' if partido.media_local > partido.media_visitante else 'visitante'
        partido.acertantes_goles = [v for v in partido.votos.all() if partido.cerrado and v.pronostico_goles == partido.opcion_goles_real]
        for winner in partido.acertantes_goles:
            penalties = winner.penalizaciones_objetivo or ({winner.objetivo_penalizacion: 50} if winner.objetivo_penalizacion else {})
            winner.penalty_distribution = list(penalties.items())
    return render(request, 'vip_matches.html', {'partidos': partidos, 'is_admin': is_admin, 'can_create_vip': can_create_vip, 'can_follow_vip': can_follow_vip, 'message': message, 'divisions': LEAGUE_MANAGERS.keys(), 'emergency_code_info': emergency_code_info})


def vip_penalty_choice(request, token):
    message = ''
    try:
        identity = signing.loads(token, salt='vip-penalty', max_age=60 * 60 * 24 * 14)
    except (signing.BadSignature, signing.SignatureExpired):
        return render(request, 'vip_penalty_choice.html', {'invalid': True})
    partido = get_object_or_404(PartidoVIP, pk=identity.get('partido'), cerrado=True)
    division = identity.get('division', '')
    manager = identity.get('manager', '')
    vote = get_object_or_404(VotoPartidoVIP, partido=partido, division=division, manager=manager, pronostico_goles=partido.opcion_goles_real)
    standings = {name: 0 for name in LEAGUE_MANAGERS.get(division, [])}
    seen_journeys = set()
    records = []
    for record in JornadaRegistro.objects.filter(division=division).order_by('jornada', '-updated_at'):
        if record.jornada not in seen_journeys:
            records.append(record)
            seen_journeys.add(record.jornada)
    for record in records:
        vip_adjustments = vip_adjustments_for_journey(record.jornada)
        for name, values in (record.datos or {}).items():
            app = int(values.get('app') or 0)
            quinielas = int(values.get('q') or 0)
            porras = int(values.get('p') or 0)
            penalty = int(values.get('penalty') or 0)
            standings[name] = standings.get(name, 0) + app + quinielas * 5 + porras * 10 - penalty + vip_adjustments.get((division, name), 0)
    general_standings = [
        {'position': position, 'manager': name, 'points': points}
        for position, (name, points) in enumerate(sorted(standings.items(), key=lambda item: (-item[1], item[0].casefold())), start=1)
    ]
    managers = [name for name in LEAGUE_MANAGERS.get(division, []) if name != manager]
    received = {name: 0 for name in managers}
    for other_vote in VotoPartidoVIP.objects.filter(partido=partido, division=division):
        penalties = other_vote.penalizaciones_objetivo or ({other_vote.objetivo_penalizacion: 50} if other_vote.objetivo_penalizacion else {})
        for target, points in penalties.items():
            received[target] = received.get(target, 0) + int(points or 0)
    if request.method == 'POST' and not vote.penalizaciones_objetivo and not vote.objetivo_penalizacion:
        allocations = {}
        invalid_amount = False
        for index, target in enumerate(managers):
            raw = request.POST.get(f'points_{index}', '0').strip() or '0'
            try:
                points = int(raw)
            except ValueError:
                invalid_amount = True
                break
            if points < 0 or points > 50:
                invalid_amount = True
                break
            if points:
                allocations[target] = points
        total = sum(allocations.values())
        if invalid_amount or total != 50:
            message = 'El reparto debe sumar exactamente 50 puntos antes de confirmarlo.'
        elif any(received.get(target, 0) + points > 150 for target, points in allocations.items()):
            message = 'Ese reparto no está disponible. Redistribuye los 50 puntos entre otros managers.'
        else:
            with transaction.atomic():
                locked_vote = VotoPartidoVIP.objects.select_for_update().get(pk=vote.pk)
                if locked_vote.penalizaciones_objetivo or locked_vote.objetivo_penalizacion:
                    message = 'Este reparto ya estaba registrado y no puede modificarse.'
                else:
                    locked_vote.penalizaciones_objetivo = allocations
                    locked_vote.save(update_fields=['penalizaciones_objetivo', 'actualizado'])
                    vote = locked_vote
                    message = f'Reparto guardado correctamente: {total} puntos en total.'
    available = [{'name': name, 'received': received.get(name, 0), 'remaining': max(0, 150 - received.get(name, 0))} for name in managers]
    saved_penalties = vote.penalizaciones_objetivo or ({vote.objetivo_penalizacion: 50} if vote.objetivo_penalizacion else {})
    return render(request, 'vip_penalty_choice.html', {'partido': partido, 'division': division, 'manager': manager, 'vote': vote, 'available': available, 'saved_penalties': saved_penalties, 'general_standings': general_standings, 'message': message, 'invalid': False})


def vip_vote(request, partido_id):
    partido = get_object_or_404(PartidoVIP, pk=partido_id)
    voting_closed = partido.cerrado or timezone.now() > partido.fecha_cierre
    position_votes = {'local': [], 'visitante': [], 'ninguno': []}
    for previous_vote in partido.votos.order_by('division', 'manager'):
        position_votes.setdefault(previous_vote.posicionamiento, []).append({'manager': previous_vote.manager, 'division': previous_vote.division})
    logo_fields = []
    preferred_local = get_preferred_team_logo(partido.equipo_local)
    preferred_visitante = get_preferred_team_logo(partido.equipo_visitante)
    if preferred_local and partido.escudo_local != preferred_local:
        partido.escudo_local = preferred_local
        logo_fields.append('escudo_local')
    elif not partido.escudo_local:
        partido.escudo_local = get_team_logo(partido.equipo_local)
        logo_fields.append('escudo_local')
    if preferred_visitante and partido.escudo_visitante != preferred_visitante:
        partido.escudo_visitante = preferred_visitante
        logo_fields.append('escudo_visitante')
    elif not partido.escudo_visitante:
        partido.escudo_visitante = get_team_logo(partido.equipo_visitante)
        logo_fields.append('escudo_visitante')
    if logo_fields and (partido.escudo_local or partido.escudo_visitante):
        partido.save(update_fields=logo_fields)
    message = ''
    selected_division = request.POST.get('division', '')
    verification_sent = False
    selected_manager = request.POST.get('manager', '')
    existing_vote = None
    if request.method == 'POST' and not voting_closed:
        action = request.POST.get('action')
        contact = ContactoManager.objects.filter(division=selected_division, manager=selected_manager).first()
        if selected_division and selected_manager:
            existing_vote = VotoPartidoVIP.objects.filter(partido=partido, division=selected_division, manager=selected_manager).first()
        if action == 'show_vote':
            verification_sent = True
            message = 'Introduce el código que recibiste para confirmar tu voto.'
        elif action == 'send_code' and contact and contact.email.lower() == request.POST.get('email', '').strip().lower():
            if existing_vote:
                message = 'Este manager ya ha votado. Cada manager solo puede votar una vez.'
                return render(request, 'vip_vote.html', {'partido': partido, 'league_managers': LEAGUE_MANAGERS, 'selected_division': selected_division, 'selected_manager': selected_manager, 'verification_sent': False, 'message': message, 'existing_vote': existing_vote, 'position_votes': position_votes, 'voting_closed': voting_closed})
            code = f'{secrets.randbelow(1000000):06d}'
            try:
                sent_count = EmailMessage(subject=f'Código de votación — {partido.titulo}', body=f'Tu código para votar es {code}. Caduca en 15 minutos.', to=[contact.email]).send(fail_silently=False)
            except Exception:
                logger.exception('No se pudo enviar el código VIP a %s (%s)', selected_manager, selected_division)
                sent_count = 0
            if sent_count:
                request.session[f'vip_code_{partido.id}'] = {'division': selected_division, 'manager': selected_manager, 'code': code, 'expires': (timezone.now() + timedelta(minutes=15)).isoformat()}
                verification_sent = True
                message = 'Código enviado correctamente. Revisa tu correo, el spam y la carpeta de promociones.'
            else:
                message = 'No se ha podido enviar el código. Inténtalo de nuevo dentro de unos segundos o avisa al administrador.'
        elif action == 'send_code':
            message = 'El correo no coincide con el registrado para ese manager.'
        elif action == 'vote':
            verification = request.session.get(f'vip_code_{partido.id}', {})
            submitted_code = request.POST.get('code', '').strip()
            valid = verification.get('division') == selected_division and verification.get('manager') == selected_manager and verification.get('code') == submitted_code and verification.get('expires', '') > timezone.now().isoformat()
            emergency_record = None
            if not valid:
                candidates = CodigoEmergenciaVIP.objects.filter(
                    partido=partido,
                    division=selected_division,
                    manager=selected_manager,
                    proposito='votar',
                    usado__isnull=True,
                    caduca__gt=timezone.now(),
                )
                emergency_record = next((item for item in candidates if check_password(submitted_code, item.codigo_hash)), None)
                valid = emergency_record is not None
            if not valid:
                message = 'El código no es correcto o ha caducado. Solicita uno nuevo.'
                verification_sent = True
            elif selected_manager in LEAGUE_MANAGERS.get(selected_division, []):
                if existing_vote:
                    message = 'Este manager ya había votado. Cada manager solo puede votar una vez.'
                    verification_sent = True
                    return render(request, 'vip_vote.html', {'partido': partido, 'league_managers': LEAGUE_MANAGERS, 'selected_division': selected_division, 'selected_manager': selected_manager, 'verification_sent': verification_sent, 'message': message, 'existing_vote': existing_vote, 'position_votes': position_votes, 'voting_closed': voting_closed})
                existing_vote = VotoPartidoVIP.objects.create(partido=partido, division=selected_division, manager=selected_manager, posicionamiento=request.POST.get('posicionamiento'), pronostico_goles=request.POST.get('pronostico_goles'), origen='usuario')
                created = True
                if emergency_record:
                    emergency_record.usado = timezone.now()
                    emergency_record.save(update_fields=['usado'])
                contact = ContactoManager.objects.filter(division=selected_division, manager=selected_manager).first()
                if contact and contact.email:
                    EmailMessage(subject=f'Voto confirmado — {partido.titulo}', body=f'Hola {selected_manager}. Tu voto para {partido.titulo} ha quedado registrado correctamente.', to=[contact.email]).send(fail_silently=True)
                request.session.pop(f'vip_code_{partido.id}', None)
                message = ('Voto guardado correctamente.' if created else 'Tu voto anterior se ha actualizado correctamente.') + ' Te hemos enviado una confirmación si tenemos tu correo.'
    return render(request, 'vip_vote.html', {'partido': partido, 'league_managers': LEAGUE_MANAGERS, 'selected_division': selected_division, 'selected_manager': selected_manager, 'verification_sent': verification_sent, 'message': message, 'existing_vote': existing_vote, 'position_votes': position_votes, 'voting_closed': voting_closed})


@login_required
def origins(request):
    coordinates = {
        'a coruna': (43.36, -8.41), 'alava': (42.85, -2.67), 'albacete': (38.99, -1.86), 'alicante': (38.35, -0.49), 'almeria': (36.84, -2.46), 'asturias': (43.36, -5.85), 'avila': (40.66, -4.70),
        'badajoz': (38.88, -6.97), 'barcelona': (41.39, 2.17), 'bizkaia': (43.26, -2.93), 'burgos': (42.34, -3.70), 'caceres': (39.48, -6.37), 'cadiz': (36.53, -6.29), 'cantabria': (43.46, -3.81),
        'castellon': (39.99, -0.04), 'ceuta': (35.89, -5.32), 'ciudad real': (38.99, -3.93), 'cordoba': (37.89, -4.78), 'cuenca': (40.07, -2.14), 'girona': (41.98, 2.82), 'granada': (37.18, -3.60),
        'guadalajara': (40.63, -3.17), 'gipuzkoa': (43.32, -1.98), 'guipuzcoa': (43.32, -1.98), 'huelva': (37.26, -6.94), 'huesca': (42.14, -0.41), 'illes balears': (39.57, 2.65), 'islas baleares': (39.57, 2.65),
        'jaen': (37.78, -3.79), 'la rioja': (42.47, -2.45), 'las palmas': (28.12, -15.44), 'leon': (42.60, -5.57), 'lleida': (41.62, 0.62), 'lugo': (43.01, -7.56), 'madrid': (40.42, -3.70),
        'malaga': (36.72, -4.42), 'melilla': (35.29, -2.94), 'murcia': (37.98, -1.13), 'navarra': (42.82, -1.64), 'ourense': (42.34, -7.86), 'palencia': (42.01, -4.53), 'pontevedra': (42.43, -8.64),
        'salamanca': (40.97, -5.66), 'santa cruz de tenerife': (28.46, -16.25), 'segovia': (40.95, -4.12), 'sevilla': (37.39, -5.98), 'soria': (41.76, -2.47), 'tarragona': (41.12, 1.25), 'teruel': (40.34, -1.11),
        'toledo': (39.86, -4.03), 'valencia': (39.47, -0.38), 'valladolid': (41.65, -4.72), 'zamora': (41.50, -5.74), 'zaragoza': (41.65, -0.89),
    }
    grouped, unresolved = {}, []
    aliases = {'coruna': 'a coruna', 'vizcaya': 'bizkaia', 'baleares': 'islas baleares'}
    for contact in ContactoManager.objects.exclude(provincia='').order_by('provincia', 'manager'):
        key = ''.join(character for character in unicodedata.normalize('NFD', contact.provincia.lower().strip()) if unicodedata.category(character) != 'Mn')
        key = aliases.get(key, key)
        point = coordinates.get(key)
        if not point:
            unresolved.append({'manager': contact.manager, 'provincia': contact.provincia, 'division': contact.division})
            continue
        item = grouped.setdefault(key, {'provincia': contact.provincia, 'lat': point[0], 'lon': point[1], 'managers': []})
        item['managers'].append({'manager': contact.manager, 'division': contact.division})
    return render(request, 'origins.html', {'markers': list(grouped.values()), 'unresolved': unresolved, 'total': ContactoManager.objects.exclude(provincia='').count()})


@login_required
def tournaments(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    if access.role == 'viewer':
        return redirect('/')
    divisions = ['Primera Divisi\u00f3n', 'Segunda Divisi\u00f3n', 'Primera RFEF', 'Segunda RFEF', 'Liga Moeve']
    return render(request, 'tournaments.html', {'divisions': divisions})


@login_required
def statistics(request):
    divisions = ['Primera División', 'Segunda División', 'Primera RFEF', 'Segunda RFEF', 'Liga Moeve']
    return render(request, 'statistics.html', {'divisions': divisions, 'jornadas': range(1, 39)})


@login_required
def vip_statistics(request):
    panels = []
    for partido in PartidoVIP.objects.prefetch_related('votos').order_by('-creado'):
        divisions = []
        for division, managers in LEAGUE_MANAGERS.items():
            votes = list(partido.votos.filter(division=division))
            record = JornadaRegistro.objects.filter(jornada=partido.jornada, division=division).order_by('-updated_at').first() if partido.jornada else None
            media_local = media_visitante = None
            positioning_winner = ''
            if partido.cerrado and record and record.cerrada:
                manager_points = {
                    name: int(row.get('app') or 0) + int(row.get('q') or 0) * 5 + int(row.get('p') or 0) * 10 - int(row.get('penalty') or 0)
                    for name, row in (record.datos or {}).items()
                }
                local_points = [manager_points[vote.manager] for vote in votes if vote.posicionamiento == 'local' and vote.manager in manager_points]
                visitor_points = [manager_points[vote.manager] for vote in votes if vote.posicionamiento == 'visitante' and vote.manager in manager_points]
                media_local = round(sum(local_points) / len(local_points), 2) if local_points else None
                media_visitante = round(sum(visitor_points) / len(visitor_points), 2) if visitor_points else None
                if media_local is not None and media_visitante is not None and media_local != media_visitante:
                    positioning_winner = partido.equipo_local if media_local > media_visitante else partido.equipo_visitante
            total = len(votes)
            positions = {key: sum(v.posicionamiento == key for v in votes) for key in ('local', 'visitante', 'ninguno')}
            goals = {key: sum(v.pronostico_goles == key for v in votes) for key in ('0', '1', '2', '3+')}
            targets = {}
            for vote in votes:
                penalties = vote.penalizaciones_objetivo or ({vote.objetivo_penalizacion: 50} if vote.objetivo_penalizacion else {})
                for target, points in penalties.items():
                    targets[target] = targets.get(target, 0) + int(points or 0)
            divisions.append({
                'name': division,
                'votes': total,
                'total': len(managers),
                'percentage': round(total * 100 / len(managers)) if managers else 0,
                'calculated': bool(partido.cerrado and record and record.cerrada),
                'media_local': media_local,
                'media_visitante': media_visitante,
                'positioning_winner': positioning_winner,
                'positions': positions,
                'goals': [
                    {'label': '0 goles', 'count': goals['0']},
                    {'label': '1 gol', 'count': goals['1']},
                    {'label': '2 goles', 'count': goals['2']},
                    {'label': '3 o más', 'count': goals['3+']},
                ],
                'targets': sorted(targets.items(), key=lambda item: (-item[1], item[0])),
            })
        panels.append({'match': partido, 'divisions': divisions})
    return render(request, 'vip_statistics.html', {'panels': panels})


@login_required
def statistics_api(request, season, jornada):
    division = request.GET.get('division', '')
    mode = request.GET.get('mode', 'round')
    queryset = JornadaRegistro.objects.filter(season=season, division=division)
    if mode != 'general':
        queryset = queryset.filter(jornada=jornada)
    else:
        try:
            through = int(request.GET.get('through', '0'))
        except ValueError:
            through = 0
        if through > 0:
            postponed = [100 + number for number in (1, 6) if number <= through]
            queryset = queryset.filter(Q(jornada__lte=through) | Q(jornada__in=postponed))
    records, seen = [], set()
    for record in queryset.order_by('jornada', '-updated_at'):
        if record.jornada not in seen:
            records.append(record)
            seen.add(record.jornada)
    totals, clause_links = {}, {}
    for record in records:
        vip_adjustments = vip_adjustments_for_journey(record.jornada)
        for manager, values in record.datos.items():
            row = totals.setdefault(manager, {'manager': manager, 'app': 0, 'quinielas': 0, 'porras': 0, 'bonus': 0, 'money': 0, 'penalty': 0, 'vip': 0, 'total': 0})
            app = int(values.get('app') or 0)
            quinielas = int(values.get('q') or 0)
            porras = int(values.get('p') or 0)
            bonus = quinielas * 5 + porras * 10
            penalty = int(values.get('penalty') or 0)
            money = int(''.join(character for character in str(values.get('money') or '') if character.isdigit()) or 0)
            row['app'] += app
            row['quinielas'] += quinielas
            row['porras'] += porras
            row['bonus'] += bonus
            row['money'] += money
            row['penalty'] += penalty
            vip = vip_adjustments.get((record.division, manager), 0)
            row['vip'] += vip
            row['total'] += app + bonus - penalty + vip
            for clause in values.get('clauses', []):
                if not isinstance(clause, dict):
                    continue
                target = clause.get('to', '').strip()
                value = int(clause.get('value') or 0)
                if target and value:
                    link = clause_links.setdefault((manager, target), {'source': manager, 'target': target, 'count': 0, 'value': 0})
                    link['count'] += 1
                    link['value'] += value
    rows = list(totals.values())
    return JsonResponse({'rows': rows, 'clause_network': list(clause_links.values()), 'closed': bool(records and all(record.cerrada for record in records)), 'journeys': len(records)})


class AppLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'login.html'

    def get_success_url(self):
        access, _ = UserAccess.objects.get_or_create(user=self.request.user)
        return '/cambiar-contrasena/' if access.must_change_password else '/'


@login_required
def change_password(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = FirstPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            access.must_change_password = False
            access.password_changed_at = timezone.now()
            access.save(update_fields=['must_change_password', 'password_changed_at'])
            return redirect('/')
    else:
        form = FirstPasswordChangeForm(request.user)
    return render(request, 'change_password.html', {'form': form})


@login_required
def _legacy_setup_collaborators(request):
    if request.user.username.casefold() != 'atleti69':
        return redirect('/')
    names = ['Kabes Team', 'LLull Team', 'Reventao', 'Carbayon']
    message = ''
    if request.method == 'POST' and request.POST.get('action') == 'create_user':
        username = request.POST.get('new_username', '').strip()
        password = request.POST.get('new_password', '')
        duration = max(1, int(request.POST.get('duration', '1') or 1))
        unit = request.POST.get('duration_unit', 'permanent')
        if username and password:
            user, _ = get_user_model().objects.get_or_create(username=username)
            user.set_password(password)
            user.save()
            expires_at = None
            if unit == 'hours':
                expires_at = timezone.now() + timedelta(hours=duration)
            elif unit == 'days':
                expires_at = timezone.now() + timedelta(days=duration)
            UserAccess.objects.update_or_create(
                user=user,
                defaults={
                    'must_change_password': True,
                    'is_viewer': True,
                    'access_expires_at': expires_at,
                },
            )
            message = f'Usuario {username} creado correctamente.'
        else:
            message = 'Es necesario indicar usuario y contraseña.'
    elif request.method == 'POST':
        for username in names:
            password = request.POST.get('password_' + username, '')
            if password:
                user, _ = get_user_model().objects.get_or_create(username=username)
                user.set_password(password)
                user.save(update_fields=['password'])
                UserAccess.objects.update_or_create(user=user, defaults={'must_change_password': True})
        message = 'Cuentas guardadas correctamente. Cada colaborador deberá cambiar su contraseña al entrar.'
    managed_users = UserAccess.objects.select_related('user').order_by('user__username')
    recent_changes = CambioRegistro.objects.select_related('usuario').order_by('-creado')[:100]
    return render(request, 'setup_collaborators.html', {
        'names': names,
        'message': message,
        'managed_users': managed_users,
        'recent_changes': recent_changes,
    })


@login_required
def setup_collaborators(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    if request.user.username.casefold() != 'atleti69' and access.role != 'admin':
        return redirect('/')
    restore_all_fixed_staff_access()
    divisions = ['Primera División', 'Segunda División', 'Primera RFEF', 'Segunda RFEF', 'Liga Moeve']
    message = ''
    if request.method == 'POST':
        action = request.POST.get('action', '')
        target_id = request.POST.get('user_id')
        if action == 'delete_user' and target_id:
            target = get_user_model().objects.filter(pk=target_id).first()
            if target and target.username.casefold() not in {username.casefold() for username in EDIT_DIVISIONS}:
                username = target.username
                target.delete()
                CambioRegistro.objects.create(usuario=request.user, jornada=0, accion='eliminar usuario', detalle={'usuario': username})
                message = f'Usuario {username} eliminado.'
        elif action == 'reset_password' and target_id:
            target = get_user_model().objects.filter(pk=target_id).first()
            new_password = request.POST.get('new_password', '')
            if target and new_password:
                target.set_password(new_password)
                target.save(update_fields=['password'])
                target_access, _ = UserAccess.objects.get_or_create(user=target)
                target_access.must_change_password = target != request.user
                target_access.save(update_fields=['must_change_password'])
                CambioRegistro.objects.create(usuario=request.user, jornada=0, accion='cambiar contrase\u00f1a', detalle={'usuario': target.username})
                message = f'Contrase\u00f1a de {target.username} actualizada.'
        elif action == 'update_user' and target_id:
            target = get_user_model().objects.filter(pk=target_id).first()
            if target:
                target_access, _ = UserAccess.objects.get_or_create(user=target)
                if target.username.casefold() not in {username.casefold() for username in EDIT_DIVISIONS}:
                    target_access.role = request.POST.get('role', 'viewer')
                    target_access.is_viewer = target_access.role == 'viewer'
                    target_access.editable_divisions = request.POST.getlist('divisions') if target_access.role == 'collaborator' else []
                    target_access.save(update_fields=['role', 'is_viewer', 'editable_divisions'])
                    CambioRegistro.objects.create(usuario=request.user, jornada=0, accion='cambiar permisos', detalle={'usuario': target.username, 'rol': target_access.role})
                    message = f'Permisos de {target.username} actualizados.'
        elif action == 'create_user':
            username = request.POST.get('new_username', '').strip()
            password = request.POST.get('new_password', '')
            role = request.POST.get('role', 'viewer')
            try:
                duration = max(1, int(request.POST.get('duration', '1') or 1))
            except ValueError:
                duration = 1
            unit = request.POST.get('duration_unit', 'permanent')
            if username and password:
                user, _ = get_user_model().objects.get_or_create(username=username)
                user.set_password(password)
                user.save()
                expires_at = timezone.now() + timedelta(hours=duration) if unit == 'hours' else timezone.now() + timedelta(days=duration) if unit == 'days' else None
                UserAccess.objects.update_or_create(user=user, defaults={
                    'must_change_password': True,
                    'is_viewer': role == 'viewer',
                    'role': role,
                    'editable_divisions': request.POST.getlist('divisions') if role == 'collaborator' else [],
                    'access_expires_at': expires_at,
                })
                CambioRegistro.objects.create(usuario=request.user, jornada=0, accion='crear usuario', detalle={'usuario': username, 'rol': role})
                message = f'Usuario {username} creado correctamente.'
            else:
                message = 'Es necesario indicar usuario y contraseña.'
    managed_users = UserAccess.objects.select_related('user').order_by('user__username')
    recent_changes = CambioRegistro.objects.select_related('usuario').order_by('-creado')[:100]
    return render(request, 'setup_collaborators.html', {'message': message, 'managed_users': managed_users, 'recent_changes': recent_changes, 'divisions': divisions})


@login_required
def dashboard(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    if access.access_expires_at and access.access_expires_at <= timezone.now():
        logout(request)
        return redirect('/login/?expired=1')
    if access.must_change_password:
        return redirect('/cambiar-contrasena/')
    if access.role == 'viewer':
        return redirect('/')
    divisions = [('Primera División', 'Kabes Team'), ('Segunda División', 'LLull Team'), ('Primera RFEF', 'Reventao'), ('Segunda RFEF', 'Carbayon'), ('Liga Moeve', 'Kabes Team')]
    users = {
        'Primera División': ['AlexJulio','Rexza','C.D.F. Arrieritos','Gestafa FC','Golden Ball','Ivanetti',"Kabe's Team",'Maceda','Mouki','Munera City','Raul C','Real JR','Iñigoool!!!!','Reventao','Tuercebotas','Llull Team','Pablo Cuevas','Joselillo81'],
        'Segunda División': ['Marina','Kataki Villenero','Carbayon','At. Aviacion','Vendy','Goyo','Rocky Team','Ruben 1903ATM','Jackobo','Baetulo','FC Almogávers','Re Creativo Igualadino','Rapido de Bouzas','Gasteiz United','eMCasa','Gabrielix de Asturin','Adrianpt260','SpartanAgain'],
        'Primera RFEF': ['Estefanía','Guerreros F.C','Pcotop Team','El Cabo','Checo21','C.D. Covadonga','Patontografos F.C','CD Cayon','Resalso','Beagar13','Gsgg Team','Manuymarian',"Minuto 94'",'JAM F.C.','Litoscaboalles','Atleti69','Maicame'],
        'Segunda RFEF': ['Semela','Soar FC','UnaiRZ','Izan Navarro','JaviArsenal','Jose Mourinho','Muñeko','Danilo77','Alex SC','K87','EmiGeta','A.A. Ponte Preta','Atletico Zaragoza','Peluso F.C.','Emilio Ramos','Sevi-21','Esta NFL No la Entiendo','Deckers'],
        'Liga Moeve': ['Titanes65','Antbariba','El Macho','Palacios FC','Real Oviedo','OskitarTeam','Jopehe95','Schalke Te meto','Caimans','Shaiel Afonso Rodriguez','RBN147','Ivan Diaz'],
    }
    legacy_allowed = fixed_edit_divisions(request.user.username)
    editable_divisions = [division for division, _ in divisions if division in legacy_allowed]
    editable_divisions.extend(access.editable_divisions)
    return render(request, 'dashboard.html', {
        'divisions': divisions,
        'users': users,
        'initial_users': next(iter(users.values())),
        'jornadas': range(1, 39),
        'editable_divisions': list(dict.fromkeys(editable_divisions)),
        'can_edit_all': request.user.username.casefold() == 'atleti69' or access.role == 'admin',
    })


@login_required
def matches_api(request, season, round_number):
    try:
        return JsonResponse({'matches': get_matches(season, round_number)})
    except Exception as exc:
        return JsonResponse({'error': 'No se pudieron actualizar los partidos', 'detail': str(exc)}, status=502)


@csrf_exempt
@login_required
def jornada_api(request, season, jornada):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    import json
    division = request.GET.get('division', '')
    if request.method == 'POST':
        try:
            division = json.loads(request.body or '{}').get('division', division)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Datos no válidos'}, status=400)
    if request.method == 'GET':
        has_vip, vip_positioning, vip_penalties = vip_breakdown_for_journey(jornada, division)
        registro = JornadaRegistro.objects.filter(season=season, jornada=jornada, division=division).order_by('-updated_at').first()
        if not registro:
            return JsonResponse({'datos': {}, 'cerrada': False, 'has_vip': has_vip, 'vip_positioning': vip_positioning, 'vip_penalties': vip_penalties})
        return JsonResponse({'datos': registro.datos, 'cerrada': registro.cerrada, 'has_vip': has_vip, 'vip_positioning': vip_positioning, 'vip_penalties': vip_penalties})
    registro, _ = JornadaRegistro.objects.get_or_create(user_access=access, season=season, jornada=jornada, division=division)
    if request.method == 'POST':
        allowed = fixed_edit_divisions(request.user.username)
        can_edit = access.role == 'admin' or '*' in allowed or division in access.editable_divisions or division in allowed
        if not can_edit:
            return JsonResponse({'error': 'Solo puedes consultar esta división'}, status=403)
        payload = json.loads(request.body or '{}')
        if registro.cerrada:
            is_admin = request.user.username.casefold() == 'atleti69' or access.role == 'admin'
            is_reopening = payload.get('cerrada') is False
            if not is_admin or not is_reopening:
                return JsonResponse({'error': 'La jornada está cerrada. Debes reabrirla antes de modificarla.'}, status=403)
        was_closed = registro.cerrada
        registro.datos = payload.get('datos', {})
        registro.cerrada = bool(payload.get('cerrada', registro.cerrada))
        registro.save(update_fields=['datos', 'cerrada', 'updated_at'])
        CambioRegistro.objects.create(usuario=request.user, division=division, season=season, jornada=jornada, accion='guardar jornada', detalle={'cerrada': registro.cerrada, 'usuarios': len(registro.datos)})
        if registro.cerrada and not was_closed:
            recipients = list(ContactoManager.objects.exclude(email='').values_list('email', flat=True).distinct())
            if recipients:
                EmailMessage(
                    subject=f'Liga Amigos XI — jornada {jornada} cerrada',
                    body=f'La jornada {jornada} de {division} ha sido cerrada. Ya puedes consultar los resultados y las clasificaciones en la aplicación.',
                    bcc=recipients,
                ).send(fail_silently=True)
        return JsonResponse({'ok': True, 'cerrada': registro.cerrada})
    return JsonResponse({'error': 'Método no permitido'}, status=405)
