from datetime import timedelta
import secrets
import unicodedata

from django.contrib.auth import get_user_model, login, logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import FirstPasswordChangeForm, LoginForm
from .models import CambioRegistro, ContactoManager, JornadaRegistro, PartidoVIP, UserAccess, VotoPartidoVIP
from .services.openligadb import get_matches, get_team_logo

EDIT_DIVISIONS = {
    'Atleti69': {'*'},
    'Kabes Team': {'Primera División', 'Liga Moeve'},
    'LLull Team': {'Segunda División'},
    'Reventao': {'Primera RFEF'},
    'Carbayon': {'Segunda RFEF'},
}

LEAGUE_MANAGERS = {
    'Primera Divisi\u00f3n': ['AlexJulio','Rexza','C.D.F. Arrieritos','Gestafa FC','Golden Ball','Ivanetti',"Kabe's Team",'Maceda','Mouki','Munera City','Raul C','Real JR','I\u00f1igoool!!!!','Reventao','Tuercebotas','Llull Team','Pablo Cuevas','Joselillo81'],
    'Segunda Divisi\u00f3n': ['Marina','Kataki Villenero','Carbayon','At. Aviacion','Vendy','Goyo','Rocky Team','Ruben 1903ATM','Jackobo','Baetulo','FC Almog\u00e1vers','Re Creativo Igualadino','Rapido de Bouzas','Gasteiz United','eMCasa','Gabrielix de Asturin','Adrianpt260','SpartanAgain'],
    'Primera RFEF': ['Estefan\u00eda','Guerreros F.C','Pcotop Team','El Cabo','Checo21','C.D. Covadonga','Patontografos F.C','CD Cayon','Resalso','Beagar13','Gsgg Team','Manuymarian',"Minuto 94'",'JAM F.C.','Litoscaboalles','Atleti69','Maicame'],
    'Segunda RFEF': ['Semela','Soar FC','UnaiRZ','Izan Navarro','JaviArsenal','Jose Mourinho','Mu\u00f1eko','Danilo77','Alex SC','K87','EmiGeta','A.A. Ponte Preta','Atletico Zaragoza','Peluso F.C.','Emilio Ramos','Sevi-21','Esta NFL No la Entiendo','Deckers'],
    'Liga Moeve': ['Titanes65','Antbariba','El Macho','Palacios FC','Real Oviedo','OskitarTeam','Jopehe95','Schalke Te meto','Caimans','Shaiel Afonso Rodriguez','RBN147','Ivan Diaz'],
}


@login_required
def home(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    if access.access_expires_at and access.access_expires_at <= timezone.now():
        logout(request)
        return redirect('/login/?expired=1')
    if access.must_change_password and request.GET.get('skip') != '1':
        return redirect('/cambiar-contrasena/')
    return render(request, 'home.html')


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
    if request.user.username != 'Atleti69' and access.role != 'admin':
        return redirect('/')
    message = ''
    if request.method == 'POST':
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
    rows = [{'division': division, 'manager': manager, 'contact': contacts.get((division, manager))} for division, managers in LEAGUE_MANAGERS.items() for manager in managers]
    share_url = request.build_absolute_uri('/actualizar-contacto/')
    return render(request, 'communications.html', {'rows': rows, 'share_url': share_url, 'completed': len(contacts), 'total': len(rows), 'message': message})


@login_required
def vip_matches(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    is_admin = request.user.username == 'Atleti69' or access.role == 'admin'
    message = ''
    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        if action == 'create':
            try:
                local = request.POST.get('equipo_local', '').strip()
                visitante = request.POST.get('equipo_visitante', '').strip()
                PartidoVIP.objects.create(
                    titulo=request.POST.get('titulo', '').strip(),
                    equipo_local=local,
                    equipo_visitante=visitante,
                    escudo_local=request.POST.get('escudo_local', '').strip() or get_team_logo(local),
                    escudo_visitante=request.POST.get('escudo_visitante', '').strip() or get_team_logo(visitante),
                    fecha_cierre=timezone.make_aware(__import__('datetime').datetime.fromisoformat(request.POST['fecha_cierre'])),
                )
                message = 'Partido VIP creado.'
            except (ValueError, KeyError):
                message = 'Revisa los datos y la fecha del partido.'
        elif action == 'close':
            partido = get_object_or_404(PartidoVIP, pk=request.POST.get('partido_id'))
            partido.goles_reales = max(0, int(request.POST.get('goles_reales', 0)))
            partido.cerrado = True
            partido.save(update_fields=['goles_reales', 'cerrado'])
            message = 'Partido cerrado y resultados calculados.'
        elif action == 'remind':
            partido = get_object_or_404(PartidoVIP, pk=request.POST.get('partido_id'))
            voted = set(partido.votos.values_list('division', 'manager'))
            recipients = [c.email for c in ContactoManager.objects.exclude(email='') if (c.division, c.manager) not in voted]
            if recipients:
                EmailMessage(subject=f'Recordatorio — {partido.titulo}', body=f'Aún no has votado en {partido.titulo}. Participa aquí: {request.build_absolute_uri(f"/partidos-vip/votar/{partido.id}/")}', bcc=recipients).send(fail_silently=True)
            message = f'Recordatorio enviado a {len(recipients)} usuarios pendientes.'
    partidos = list(PartidoVIP.objects.prefetch_related('votos').order_by('-creado'))
    manager_points = {}
    for registro in JornadaRegistro.objects.all():
        for manager, row in (registro.datos or {}).items():
            total = int(row.get('app') or 0) + int(row.get('q') or 0) * 5 + int(row.get('p') or 0) * 10 - int(row.get('penalty') or 0)
            manager_points[(registro.division, manager)] = manager_points.get((registro.division, manager), 0) + total
    for partido in partidos:
        logo_fields = []
        if not partido.escudo_local:
            partido.escudo_local = get_team_logo(partido.equipo_local)
            logo_fields.append('escudo_local')
        if not partido.escudo_visitante:
            partido.escudo_visitante = get_team_logo(partido.equipo_visitante)
            logo_fields.append('escudo_visitante')
        if logo_fields and (partido.escudo_local or partido.escudo_visitante):
            partido.save(update_fields=logo_fields)
        partido.vote_url = request.build_absolute_uri(f'/partidos-vip/votar/{partido.id}/')
        partido.participantes = partido.votos.count()
        groups = {'local': [], 'visitante': []}
        for vote in partido.votos.all():
            if vote.posicionamiento in groups:
                groups[vote.posicionamiento].append(manager_points.get((vote.division, vote.manager), 0))
        partido.media_local = round(sum(groups['local']) / len(groups['local']), 2) if groups['local'] else None
        partido.media_visitante = round(sum(groups['visitante']) / len(groups['visitante']), 2) if groups['visitante'] else None
        partido.ganador_posicionamiento = ''
        if partido.media_local is not None and partido.media_visitante is not None and partido.media_local != partido.media_visitante:
            partido.ganador_posicionamiento = 'local' if partido.media_local > partido.media_visitante else 'visitante'
        partido.acertantes_goles = [v for v in partido.votos.all() if partido.cerrado and v.pronostico_goles == partido.opcion_goles_real]
    return render(request, 'vip_matches.html', {'partidos': partidos, 'is_admin': is_admin, 'message': message, 'divisions': LEAGUE_MANAGERS.keys()})


def vip_vote(request, partido_id):
    partido = get_object_or_404(PartidoVIP, pk=partido_id)
    logo_fields = []
    if not partido.escudo_local:
        partido.escudo_local = get_team_logo(partido.equipo_local)
        logo_fields.append('escudo_local')
    if not partido.escudo_visitante:
        partido.escudo_visitante = get_team_logo(partido.equipo_visitante)
        logo_fields.append('escudo_visitante')
    if logo_fields and (partido.escudo_local or partido.escudo_visitante):
        partido.save(update_fields=logo_fields)
    message = ''
    selected_division = request.POST.get('division', '')
    verification_sent = False
    selected_manager = request.POST.get('manager', '')
    if request.method == 'POST' and not partido.cerrado and timezone.now() <= partido.fecha_cierre:
        action = request.POST.get('action')
        contact = ContactoManager.objects.filter(division=selected_division, manager=selected_manager).first()
        if action == 'send_code' and contact and contact.email.lower() == request.POST.get('email', '').strip().lower():
            code = f'{secrets.randbelow(1000000):06d}'
            request.session[f'vip_code_{partido.id}'] = {'division': selected_division, 'manager': selected_manager, 'code': code, 'expires': (timezone.now() + timedelta(minutes=15)).isoformat()}
            EmailMessage(subject=f'Código de votación — {partido.titulo}', body=f'Tu código para votar es {code}. Caduca en 15 minutos.', to=[contact.email]).send(fail_silently=True)
            verification_sent = True
            message = 'Código enviado. Revisa tu correo e introdúcelo para votar.'
        elif action == 'send_code':
            message = 'El correo no coincide con el registrado para ese manager.'
        elif action == 'vote':
            verification = request.session.get(f'vip_code_{partido.id}', {})
            valid = verification.get('division') == selected_division and verification.get('manager') == selected_manager and verification.get('code') == request.POST.get('code', '').strip() and verification.get('expires', '') > timezone.now().isoformat()
            if not valid:
                message = 'El código no es correcto o ha caducado. Solicita uno nuevo.'
                verification_sent = True
            elif selected_manager in LEAGUE_MANAGERS.get(selected_division, []):
                VotoPartidoVIP.objects.update_or_create(partido=partido, division=selected_division, manager=selected_manager, defaults={'posicionamiento': request.POST.get('posicionamiento'), 'pronostico_goles': request.POST.get('pronostico_goles')})
                contact = ContactoManager.objects.filter(division=selected_division, manager=selected_manager).first()
                if contact and contact.email:
                    EmailMessage(subject=f'Voto confirmado — {partido.titulo}', body=f'Hola {selected_manager}. Tu voto para {partido.titulo} ha quedado registrado correctamente.', to=[contact.email]).send(fail_silently=True)
                request.session.pop(f'vip_code_{partido.id}', None)
                message = 'Voto guardado correctamente. Te hemos enviado una confirmación si tenemos tu correo.'
    return render(request, 'vip_vote.html', {'partido': partido, 'league_managers': LEAGUE_MANAGERS, 'selected_division': selected_division, 'selected_manager': selected_manager, 'verification_sent': verification_sent, 'message': message})


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
    divisions = ['Primera Divisi\u00f3n', 'Segunda Divisi\u00f3n', 'Primera RFEF', 'Segunda RFEF', 'Liga Moeve']
    return render(request, 'tournaments.html', {'divisions': divisions})


@login_required
def statistics(request):
    divisions = ['Primera División', 'Segunda División', 'Primera RFEF', 'Segunda RFEF', 'Liga Moeve']
    return render(request, 'statistics.html', {'divisions': divisions, 'jornadas': range(1, 39)})


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
        for manager, values in record.datos.items():
            row = totals.setdefault(manager, {'manager': manager, 'app': 0, 'quinielas': 0, 'porras': 0, 'bonus': 0, 'money': 0, 'penalty': 0, 'total': 0})
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
            row['total'] += app + bonus - penalty
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
    if request.user.username != 'Atleti69':
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
    if request.user.username != 'Atleti69' and access.role != 'admin':
        return redirect('/')
    divisions = ['Primera División', 'Segunda División', 'Primera RFEF', 'Segunda RFEF', 'Liga Moeve']
    message = ''
    if request.method == 'POST':
        action = request.POST.get('action', '')
        target_id = request.POST.get('user_id')
        if action == 'delete_user' and target_id:
            target = get_user_model().objects.filter(pk=target_id).first()
            if target and target.username != 'Atleti69':
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
                if target.username != 'Atleti69':
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
    if access.access_expires_at and access.access_expires_at <= timezone.now():
        logout(request)
        return redirect('/login/?expired=1')
    if access.must_change_password:
        return redirect('/cambiar-contrasena/')
    divisions = [('Primera División', 'Kabes Team'), ('Segunda División', 'LLull Team'), ('Primera RFEF', 'Reventao'), ('Segunda RFEF', 'Carbayon'), ('Liga Moeve', 'Kabes Team')]
    users = {
        'Primera División': ['AlexJulio','Rexza','C.D.F. Arrieritos','Gestafa FC','Golden Ball','Ivanetti',"Kabe's Team",'Maceda','Mouki','Munera City','Raul C','Real JR','Iñigoool!!!!','Reventao','Tuercebotas','Llull Team','Pablo Cuevas','Joselillo81'],
        'Segunda División': ['Marina','Kataki Villenero','Carbayon','At. Aviacion','Vendy','Goyo','Rocky Team','Ruben 1903ATM','Jackobo','Baetulo','FC Almogávers','Re Creativo Igualadino','Rapido de Bouzas','Gasteiz United','eMCasa','Gabrielix de Asturin','Adrianpt260','SpartanAgain'],
        'Primera RFEF': ['Estefanía','Guerreros F.C','Pcotop Team','El Cabo','Checo21','C.D. Covadonga','Patontografos F.C','CD Cayon','Resalso','Beagar13','Gsgg Team','Manuymarian',"Minuto 94'",'JAM F.C.','Litoscaboalles','Atleti69','Maicame'],
        'Segunda RFEF': ['Semela','Soar FC','UnaiRZ','Izan Navarro','JaviArsenal','Jose Mourinho','Muñeko','Danilo77','Alex SC','K87','EmiGeta','A.A. Ponte Preta','Atletico Zaragoza','Peluso F.C.','Emilio Ramos','Sevi-21','Esta NFL No la Entiendo','Deckers'],
        'Liga Moeve': ['Titanes65','Antbariba','El Macho','Palacios FC','Real Oviedo','OskitarTeam','Jopehe95','Schalke Te meto','Caimans','Shaiel Afonso Rodriguez','RBN147','Ivan Diaz'],
    }
    legacy_allowed = EDIT_DIVISIONS.get(request.user.username, set())
    editable_divisions = [division for division, _ in divisions if division in legacy_allowed]
    editable_divisions.extend(access.editable_divisions)
    return render(request, 'dashboard.html', {
        'divisions': divisions,
        'users': users,
        'initial_users': next(iter(users.values())),
        'jornadas': range(1, 39),
        'editable_divisions': list(dict.fromkeys(editable_divisions)),
        'can_edit_all': request.user.username == 'Atleti69' or access.role == 'admin',
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
    import json
    division = request.GET.get('division', '')
    if request.method == 'POST':
        try:
            division = json.loads(request.body or '{}').get('division', division)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Datos no válidos'}, status=400)
    if request.method == 'GET':
        registro = JornadaRegistro.objects.filter(season=season, jornada=jornada, division=division).order_by('-updated_at').first()
        if not registro:
            return JsonResponse({'datos': {}, 'cerrada': False})
        return JsonResponse({'datos': registro.datos, 'cerrada': registro.cerrada})
    registro, _ = JornadaRegistro.objects.get_or_create(user_access=access, season=season, jornada=jornada, division=division)
    if request.method == 'POST':
        allowed = EDIT_DIVISIONS.get(request.user.username, set())
        can_edit = access.role == 'admin' or '*' in allowed or division in access.editable_divisions or division in allowed
        if not can_edit:
            return JsonResponse({'error': 'Solo puedes consultar esta división'}, status=403)
        payload = json.loads(request.body or '{}')
        if registro.cerrada:
            is_admin = request.user.username == 'Atleti69' or access.role == 'admin'
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
