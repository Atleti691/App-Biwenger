from django.contrib.auth import login
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from .forms import FirstPasswordChangeForm, LoginForm
from .models import JornadaRegistro, UserAccess
from .services.openligadb import get_matches


@login_required
def home(request):
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    if access.must_change_password:
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
    return render(request, 'dashboard.html', {'divisions': divisions, 'users': users, 'jornadas': range(1, 39)})


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
    registro, _ = JornadaRegistro.objects.get_or_create(user_access=access, season=season, jornada=jornada)
    if request.method == 'GET':
        return JsonResponse({'datos': registro.datos, 'cerrada': registro.cerrada})
    if request.method == 'POST':
        if registro.cerrada and request.user.username != 'Atleti69':
            return JsonResponse({'error': 'La jornada está cerrada'}, status=403)
        import json
        payload = json.loads(request.body or '{}')
        registro.datos = payload.get('datos', {})
        registro.cerrada = bool(payload.get('cerrada', registro.cerrada))
        registro.save(update_fields=['datos', 'cerrada', 'updated_at'])
        return JsonResponse({'ok': True, 'cerrada': registro.cerrada})
    return JsonResponse({'error': 'Método no permitido'}, status=405)
