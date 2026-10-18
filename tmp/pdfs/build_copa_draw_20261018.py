"""Snapshot of the saved draw, read from the live Copa page on 18 October 2026."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from pypdf import PdfReader

PAIRS = [
    ('Re Creativo Igualadino', 'Gabrielix de Asturin'),
    ('Reventao', 'SpartanAgain'), ('Tuercebotas', 'OskitarTeam'),
    ('Real Oviedo', 'Titanes65'), ("Kabe's Team", 'RBN147'),
    ('Jackobo', 'Checo21'), ('Sevi-21', 'CD Cayon'),
    ('Rocky Team', 'At. Aviacion'), ('Resalso', 'Adrianpt260'),
    ('Litoscaboalles', 'Semela'), ('Estefanía', 'Mouki'),
    ('Raul C', 'C.D.F. Arrieritos'), ('Manuymarian', 'Antbariba'),
    ('Deckers', 'K87'), ('Emilio Ramos', 'Pablo Cuevas'),
    ('Ivan Diaz', 'EmiGeta'),
]
ROOT = Path(__file__).resolve().parents[2]
path = ROOT / 'output/pdf/copa-del-rey-cuadro-cruces-2026.pdf'
path.parent.mkdir(parents=True, exist_ok=True)
W, H = landscape(A3)
c = canvas.Canvas(str(path), pagesize=(W,H))
c.setTitle('Copa del Rey - El camino hacia la final - Liga Amigos XI')
c.setAuthor('Liga Amigos XI')
c.setFillColor(HexColor('#f4f6fb')); c.rect(0,0,W,H,fill=1,stroke=0)
c.setFillColor(HexColor('#182144')); c.rect(0,H-89,W,89,fill=1,stroke=0)
c.setFillColor(HexColor('#ffffff')); c.setFont('Helvetica-Bold',27)
c.drawString(32,H-40,'COPA DEL REY')
c.setFont('Helvetica',13); c.drawString(32,H-66,'Liga Amigos XI  |  El camino hacia la final')
c.setFont('Helvetica-Bold',11); c.drawRightString(W-32,H-40,'32 MANAGERS · 1 CAMPEÓN')
c.setFont('Helvetica',9); c.drawRightString(W-32,H-63,'Cuadro consultado el 18/10/2026')
cols = [('DIECISEISAVOS','J12 + J13'),('OCTAVOS','J14 + J15'),('CUARTOS','J16 + J17'),('SEMIFINALES','J18 + J19'),('FINAL','J36 · Partido único')]
margin, gap = 32, 26
bw = (W-2*margin-4*gap)/5
xs = [margin+i*(bw+gap) for i in range(5)]
centers = [[H-147-i*41 for i in range(16)]]
for _ in range(4):
    previous=centers[-1]
    centers.append([(previous[i]+previous[i+1])/2 for i in range(0,len(previous),2)])
for r in range(4):
    c.setStrokeColor(HexColor('#9baac5')); c.setLineWidth(1)
    for i,y in enumerate(centers[r]):
        nx,ny=xs[r+1],centers[r+1][i//2]
        mid=xs[r]+bw+gap/2
        c.lines([(xs[r]+bw,y,mid,y),(mid,y,mid,ny),(mid,ny,nx,ny)])
for r,(label,journeys) in enumerate(cols):
    x=xs[r]
    c.setFillColor(HexColor('#182144')); c.setFont('Helvetica-Bold',11); c.drawString(x,H-110,label)
    c.setFillColor(HexColor('#63718a')); c.setFont('Helvetica',9); c.drawString(x,H-124,journeys)
    for i,y in enumerate(centers[r]):
        bh=34 if r==0 else 46
        c.setFillColor(HexColor('#ffffff')); c.setStrokeColor(HexColor('#ccd5e5'))
        c.roundRect(x,y-bh/2,bw,bh,5,fill=1,stroke=1)
        c.setFillColor(HexColor('#ed174c')); c.setFont('Helvetica-Bold',5.8)
        c.drawString(x+7,y+bh/2-8,f'CRUCE {i+1}')
        rows=PAIRS[i] if r==0 else (f'Ganador cruce {2*i+1} de {cols[r-1][0].lower()}', f'Ganador cruce {2*i+2} de {cols[r-1][0].lower()}')
        c.setFillColor(HexColor('#182144'))
        for j,text in enumerate(rows):
            size=8 if r==0 else 7.4
            while stringWidth(text,'Helvetica-Bold',size)>bw-15:
                size-=.2
            c.setFont('Helvetica-Bold',size)
            c.drawString(x+7,y+(2 if r==0 else 3)-j*11,text)
        if r==4:
            c.setFillColor(HexColor('#ed174c'))
            c.setFont('Helvetica-Bold',13); c.drawCentredString(x+bw/2,y-57,'EL TÍTULO TE ESPERA')
c.setFillColor(HexColor('#63718a')); c.setFont('Helvetica',8)
c.drawString(32,25,'Ida y vuelta hasta semifinales · Solo puntos APP · Los cruces avanzan siguiendo las líneas del cuadro.')
c.drawRightString(W-32,25,'Consulta el cuadro actualizado en la aplicación')
c.linkURL('https://liga-amigos-xi.onrender.com/torneos/copa-del-rey/',(32,12,W-32,38),relative=0)
c.save()
reader=PdfReader(path)
assert len(reader.pages)==1
text=reader.pages[0].extract_text()
assert all(name in text for pair in PAIRS for name in pair)
assert len(set(name for pair in PAIRS for name in pair))==32
print(f'PDF verificado: 1 página, 32 managers, 16 cruces. {path}')
