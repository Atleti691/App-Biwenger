from django.contrib.auth import get_user_model, login
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from .forms import FirstPasswordChangeForm, LoginForm
from .models import CambioRegistro, JornadaRegistro, UserAccess
from .services.openligadb import get_matches


@login_required
def home(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    if access.must_change_password and request.GET.get('skip') != '1':
        return redirect('/cambiar-contrasena/')
    return render(request, 'home.html')


def public_home(request):
    return render(request, 'public_home.html')


@login_required
def tournaments(request):
    return render(request, 'tournaments.html')


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
def setup_collaborators(request):
    if request.user.username != 'Atleti69':
        return redirect('/')
    names = ['Kabes Team', 'LLull Team', 'Reventao', 'Carbayon']
    message = ''
    if request.method == 'POST':
        for username in names:
            password = request.POST.get('password_' + username, '')
            if password:
                user, _ = get_user_model().objects.get_or_create(username=username)
                user.set_password(password)
                user.save(update_fields=['password'])
                UserAccess.objects.update_or_create(user=user, defaults={'must_change_password': True})
        message = 'Cuentas guardadas correctamente. Cada colaborador deberá cambiar su contraseña al entrar.'
    return render(request, 'setup_collaborators.html', {'names': names, 'message': message})


@login_required
def dashboard(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
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
    return render(request, 'dashboard.html', {'divisions': divisions, 'users': users, 'initial_users': next(iter(users.values())), 'jornadas': range(1, 39)})


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
        registro = JornadaRegistro.objects.filter(user_access=access, season=season, jornada=jornada, division=division).first()
        if not registro:
            return JsonResponse({'datos': {}, 'cerrada': False})
        return JsonResponse({'datos': registro.datos, 'cerrada': registro.cerrada})
    registro, _ = JornadaRegistro.objects.get_or_create(user_access=access, season=season, jornada=jornada, division=division)
    if request.method == 'POST':
        if registro.cerrada and request.user.username != 'Atleti69':
            return JsonResponse({'error': 'La jornada está cerrada'}, status=403)
        payload = json.loads(request.body or '{}')
        registro.datos = payload.get('datos', {})
        registro.cerrada = bool(payload.get('cerrada', registro.cerrada))
        registro.save(update_fields=['datos', 'cerrada', 'updated_at'])
        CambioRegistro.objects.create(usuario=request.user, division=division, season=season, jornada=jornada, accion='guardar jornada', detalle={'cerrada': registro.cerrada, 'usuarios': len(registro.datos)})
        return JsonResponse({'ok': True, 'cerrada': registro.cerrada})
    return JsonResponse({'error': 'Método no permitido'}, status=405)
