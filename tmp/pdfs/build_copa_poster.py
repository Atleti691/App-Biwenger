from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/copa-del-rey-guia-clasificacion.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold', 'C:/Windows/Fonts/arialbd.ttf'))
NAVY, RED, GOLD, INK = '#18152f', '#ee2449', '#d9b15f', '#262638'
c = canvas.Canvas(str(OUT), pagesize=(595, 842))
c.setTitle('Copa del Rey - Liga Amigos XI - Guía de clasificación')
c.setAuthor('Liga Amigos XI')

def rect(x, y, w, h, color, radius=0):
    c.setFillColor(HexColor(color))
    if radius: c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
    else: c.rect(x, y, w, h, fill=1, stroke=0)

def text(x, y, value, size=12, color=INK, bold=False):
    c.setFillColor(HexColor(color)); c.setFont('ArialBold' if bold else 'Arial', size)
    c.drawString(x, y, value)

def para(x, top, value, width=499, size=12, color=INK):
    style = ParagraphStyle('body', fontName='Arial', fontSize=size, leading=size*1.4,
                           textColor=HexColor(color))
    p = Paragraph(value, style); _, h = p.wrap(width, 500)
    p.drawOn(c, x, top-h)
    return h

def footer(page):
    rect(0, 0, 595, 38, NAVY)
    text(34, 15, 'LIGA AMIGOS XI  /  TEMPORADA 2026', 9, '#ffffff', True)
    text(500, 15, f'{page} / 3', 9, '#ffffff')

def background():
    rect(0, 0, 595, 842, '#f6f4ef')

background()
rect(0, 606, 595, 236, NAVY)
rect(34, 796, 240, 23, RED, 6)
text(45, 803, 'ÚLTIMA JORNADA PARA CLASIFICARSE', 10, '#ffffff', True)
text(34, 753, 'LA COPA', 44, '#ffffff', True)
text(34, 705, 'NOS ESPERA.', 44, '#ffffff', True)
text(36, 666, 'Todo se decide al terminar la jornada 8.', 14, '#ffffff')
text(36, 636, '32 managers. Un sorteo. Una copa.', 13, GOLD, True)
rect(431, 701, 129, 129, '#ffffff', 18)
c.drawImage(str(ROOT/'core/assets/tournaments/copa-rey.png'), 443, 711, 105, 108,
            preserveAspectRatio=True, anchor='c', mask='auto')

text(34, 574, '¿QUIÉN CONSIGUE SU PLAZA?', 19, NAVY, True)
para(34, 554, 'Se clasifican los <b>seis mejores de la clasificación general de cada división</b> '
     'al finalizar la J8. Las plazas aún pueden cambiar durante esta última jornada.', size=12)

divisions = ['Primera División', 'Segunda División', 'Primera RFEF', 'Segunda RFEF', 'Liga Moeve']
for i, division in enumerate(divisions):
    y = 453-i*35
    rect(34, y, 527, 29, '#ffffff', 7)
    text(47, y+9, division, 12, NAVY, True)
    text(465, y+9, '6 PLAZAS', 11, RED, True)

rect(34, 189, 527, 106, '#eae6dc', 12)
text(49, 272, 'DOS INVITADOS YA CLASIFICADOS', 13, NAVY, True)
text(49, 245, 'Raul C', 15, NAVY, True)
text(309, 245, 'Gabrielix de Asturin', 15, NAVY, True)
text(49, 226, 'Primera División', 10)
text(309, 226, 'Segunda División', 10)
para(49, 217, 'Invitados por ser <b>ganadores de la clasificación general de quinielas</b> '
     'de la temporada anterior, en la que <b>no se disputó la Copa del Rey</b>.', width=493, size=9)

para(34, 167, '<b>Sin plazas duplicadas:</b> si un invitado está entre los seis primeros, se salta '
     'su nombre y entra el siguiente manager elegible de esa división. '
     '<b>30 plazas por clasificación + 2 invitados = 32 participantes.</b>', size=11)
para(34, 98, '<b>Consulta la lista provisional en la página 3.</b> Los dos invitados tienen plaza '
     'asegurada. Las otras 30 plazas se confirmarán al cerrar la jornada 8. '
     'Listado facilitado por la organización el 6 de octubre de 2026.', size=10, color='#656575')
footer(1); c.showPage()

background()
rect(0, 695, 595, 147, NAVY)
text(34, 799, 'EL CAMINO HASTA LA COPA', 24, '#ffffff', True)
text(34, 766, 'Sorteo aleatorio entre los 32 clasificados.', 14, GOLD, True)
para(34, 746, 'La clasificación se cierra tras la J8. Las eliminatorias empiezan en la J12. '
     'El sorteo fijará los cruces y el camino hasta la final.', size=11, color='#ffffff')

stages = [('32', 'DIECISEISAVOS', 'J12 ida  /  J13 vuelta', '16 clasificados'),
          ('16', 'OCTAVOS', 'J14 ida  /  J15 vuelta', '8 clasificados'),
          ('8', 'CUARTOS', 'J16 ida  /  J17 vuelta', '4 clasificados'),
          ('4', 'SEMIFINALES', 'J18 ida  /  J19 vuelta', '2 finalistas'),
          ('2', 'FINAL', 'J36  /  partido único', 'Un campeón')]
for i, (number, name, date, result) in enumerate(stages):
    y = 593-i*67
    rect(34, y, 527, 57, '#ffffff', 10)
    rect(46, y+8, 43, 41, RED if i==4 else NAVY, 8)
    text(55, y+21, number, 20, '#ffffff', True)
    text(105, y+36, name, 12, NAVY, True)
    text(105, y+17, date, 11)
    text(432, y+25, result, 10, RED, True)

text(34, 291, 'CÓMO SE DECIDE QUIÉN PASA', 16, NAVY, True)
para(34, 275, 'En cada cruce cuentan <b>solo los puntos APP</b> de las jornadas de la eliminatoria. '
     'En ida y vuelta se suman ambas puntuaciones; gana quien consiga más puntos. '
     'No cuentan quinielas, porras ni ajustes adicionales.', size=11)
para(34, 219, '<b>Desempate:</b> 1) más goles; 2) más asistencias; 3) menos tarjetas. '
     'Se suman los datos de ambas jornadas (solo J36 en la final). Los administradores '
     'aportarán los datos de Biwenger únicamente si hay empate. Cada amarilla y cada roja '
     'cuentan una tarjeta. Si persiste el empate, queda pendiente de resolver.', size=10)

rect(34, 94, 527, 65, NAVY, 12)
text(49, 136, 'PREMIOS QUE SUMAN EN LA LIGA', 12, GOLD, True)
text(49, 111, '+15 por pasar ronda', 12, '#ffffff', True)
text(271, 111, 'Campeón +50  /  Subcampeón +25', 11, '#ffffff', True)
para(34, 81, 'Los +15 se anotan en J13, J15, J17 y J19; los premios finales, en J36. '
     'Consulta el cuadro y los resultados en Torneos > Copa del Rey.', size=10)
c.linkURL('https://liga-amigos-xi.onrender.com/torneos/', (34,45,560,83), relative=0)
footer(2); c.showPage()

background()
rect(0, 699, 595, 143, NAVY)
text(34, 798, 'AHORA MISMO, EN LA COPA', 23, '#ffffff', True)
text(34, 767, 'Clasificados provisionales  /  6 de octubre de 2026', 12, GOLD, True)
para(34, 744, '30 plazas por clasificación y 2 invitados directos. La lista ordinaria puede '
     'cambiar hasta el cierre de J8. El orden de los nombres no representa los cruces del sorteo.',
     size=11, color='#ffffff')
groups = [
    ('Primera División', ['Raul C', 'Pablo Cuevas', "Kabe's Team", 'Reventao', 'Mouki', 'Tuercebotas', 'C.D.F. Arrieritos']),
    ('Segunda División', ['Gabrielix de Asturin', 'SpartanAgain', 'Rapido de Bouzas', 'Jackobo', 'At. Aviacion', 'Re Creativo Igualadino', 'Baetulo']),
    ('Primera RFEF', ['Estefanía', 'Manuymarian', 'Checo21', 'Resalso', 'Gsgg Team', 'Litoscaboalles']),
    ('Segunda RFEF', ['Semela', 'Sevi-21', 'K87', 'Deckers', 'Emilio Ramos', 'EmiGeta']),
    ('Liga Moeve', ['RBN147', 'Ivan Diaz', 'OskitarTeam', 'Real Oviedo', 'Antbariba', 'Titanes65']),
]
assert sum(len(names) for _, names in groups) == 32
assert len({(division, name) for division, names in groups for name in names}) == 32
for index, (division, names) in enumerate(groups):
    y = 560-index*108
    rect(34, y, 527, 98, '#ffffff', 12)
    text(49, y+77, division.upper(), 12, NAVY, True)
    text(462, y+77, f'{len(names)} managers', 10, RED, True)
    for position, name in enumerate(names):
        column, line = position % 2, position // 2
        guest = name in ('Raul C', 'Gabrielix de Asturin')
        label = name + (' *' if guest else '')
        text(49+column*256, y+57-line*15, label, 10.5, RED if guest else INK, guest)
para(34, 109, '<b>* Invitados con plaza asegurada:</b> ganadores de la general de quinielas '
     'de la temporada anterior, en la que no se disputó la Copa del Rey. '
     'Fuente del listado: organización de Liga Amigos XI.', size=10)
footer(3); c.save()
print(OUT)
