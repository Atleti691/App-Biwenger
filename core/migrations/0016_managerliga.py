from django.db import migrations, models


MANAGERS = {
    'Primera División': ['AlexJulio','Rexza','C.D.F. Arrieritos','Gestafa FC','Golden Ball','Ivanetti',"Kabe's Team",'Maceda','Mouki','Munera City','Raul C','Real JR','Iñigoool!!!!','Reventao','Tuercebotas','Llull Team','Pablo Cuevas','Joselillo81'],
    'Segunda División': ['Marina','Kataki Villenero','Carbayon','At. Aviacion','Vendy','Goyo','Rocky Team','Ruben 1903ATM','Jackobo','Baetulo','FC Almogávers','Re Creativo Igualadino','Rapido de Bouzas','Gasteiz United','eMCasa','Gabrielix de Asturin','Adrianpt260','SpartanAgain'],
    'Primera RFEF': ['Estefanía','Guerreros F.C','Pcotop Team','El Cabo','Checo21','C.D. Covadonga','Patontografos F.C','CD Cayon','Resalso','Beagar13','Gsgg Team','Manuymarian',"Minuto 94'",'JAM F.C.','Litoscaboalles','Atleti69','Maicame'],
    'Segunda RFEF': ['Semela','Soar FC','UnaiRZ','Izan Navarro','JaviArsenal','Jose Mourinho','Muñeko','Danilo77','Alex SC','K87','EmiGeta','A.A. Ponte Preta','Atletico Zaragoza','Peluso F.C.','Emilio Ramos','Sevi-21','Esta NFL No la Entiendo','Deckers'],
    'Liga Moeve': ['Titanes65','Antbariba','El Macho','Palacios FC','Real Oviedo','OskitarTeam','Jopehe95','Schalke Te meto','Caimans','Shaiel Afonso Rodriguez','RBN147','Ivan Diaz'],
}


def seed_managers(apps, schema_editor):
    ManagerLiga = apps.get_model('core', 'ManagerLiga')
    ManagerLiga.objects.bulk_create([
        ManagerLiga(season=2026, division=division, manager=manager, activo=True)
        for division, managers in MANAGERS.items() for manager in managers
    ], ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [('core', '0015_partidovip_notificaciones_ganadores')]
    operations = [
        migrations.CreateModel(
            name='ManagerLiga',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('season', models.PositiveIntegerField(default=2026)),
                ('division', models.CharField(max_length=80)),
                ('manager', models.CharField(max_length=120)),
                ('activo', models.BooleanField(default=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ('division', 'manager'), 'unique_together': {('season', 'division', 'manager')}},
        ),
        migrations.RunPython(seed_managers, migrations.RunPython.noop),
    ]
