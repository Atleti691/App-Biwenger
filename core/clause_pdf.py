"""Read-only clause exports with the same scope as the statistics screen."""
from io import BytesIO
import json
from math import ceil
from xml.sax.saxutils import escape

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .journeys import journey_label


PALETTE = [('#f7d4d6', '#82242a'), ('#d4efda', '#174d2c'), ('#244e8a', '#ffffff')]


def heat_colors(count, maximum):
    if not count:
        return '#eef2f8', '#56647a'
    index = 0 if count <= ceil(maximum / 3) else 1 if count <= ceil(maximum * 2 / 3) else 2
    return PALETTE[index]


def build_clause_pdf(links, division, period, manager=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    stream = BytesIO()
    heatmap = manager is None
    size = landscape(A4) if heatmap else A4
    doc = SimpleDocTemplate(stream, pagesize=size, leftMargin=32, rightMargin=32,
                           topMargin=32, bottomMargin=38,
                           title='Mapa de cláusulas' if heatmap else f'Cláusulas - {manager}', author='Liga Amigos XI')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Compact', fontName='Helvetica', fontSize=8, leading=10))
    styles.add(ParagraphStyle('SmallCell', fontName='Helvetica', fontSize=7, leading=8))
    def p(value, style='Normal'):
        return Paragraph(escape(str(value)), styles[style])
    def money(value):
        return f'{int(value):,}'.replace(',', '.') + ' €'
    def footer(c, document):
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#627087'))
        c.drawString(32, 20, 'Liga Amigos XI · Exportación de estadísticas')
        c.drawRightString(size[0] - 32, 20, f'Página {document.page}')
    title = 'Mapa de calor de cláusulas' if heatmap else f'Detalle de cláusulas: {manager}'
    story = [p(title, 'Title'), p(f'{division} · {period}', 'Heading3'), Spacer(1, 12)]
    if heatmap:
        names = sorted({name for item in links for name in (item['source'], item['target'])}, key=str.casefold)
        ids = {name: index + 1 for index, name in enumerate(names)}
        maximum = max((int(item['count']) for item in links), default=1)
        lookup = {(item['source'], item['target']): int(item['count']) for item in links}
        story += [p('Filas: realiza la cláusula. Columnas: la recibe. Cada celda indica el número de cláusulas.', 'Compact')]
        legend = Table([['Sin cláusulas', 'Frecuencia baja', 'Frecuencia media', 'Frecuencia alta']], colWidths=[doc.width / 4]*4)
        legend.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#eef2f8'))]
            + [('BACKGROUND', (i+1, 0), (i+1, 0), colors.HexColor(bg)) for i, (bg, _) in enumerate(PALETTE)]
            + [('TEXTCOLOR', (i+1, 0), (i+1, 0), colors.HexColor(fg)) for i, (_, fg) in enumerate(PALETTE)]
            + [('FONTSIZE', (0, 0), (-1, -1), 9), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 8)]))
        story += [Spacer(1, 8), legend, Spacer(1, 12)]
        chunks = [names[index:index+18] for index in range(0, len(names), 18)]
        if not names:
            story.append(p('No hay cláusulas con manager de destino en este periodo.'))
        for ri, row_names in enumerate(chunks):
            for ci, column_names in enumerate(chunks):
                if ri or ci:
                    story += [PageBreak(), p(title, 'Heading1'), p(f'{division} · {period}', 'Heading3')]
                story.append(p('Columnas numeradas: consulta la clave de managers al final del documento.', 'Compact'))
                cells = [[p('Realiza / Recibe', 'Compact')] + [str(ids[name]) for name in column_names]]
                commands = [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6edf9')),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
                            ('ALIGN', (1, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.white)]
                for row_index, source in enumerate(row_names, 1):
                    cells.append([p(f'{ids[source]}. {source}', 'SmallCell')] + [str(lookup.get((source, target), 0)) or '0' for target in column_names])
                    for col_index, target in enumerate(column_names, 1):
                        bg, fg = heat_colors(lookup.get((source, target), 0), maximum)
                        commands += [('BACKGROUND', (col_index, row_index), (col_index, row_index), colors.HexColor(bg)),
                                     ('TEXTCOLOR', (col_index, row_index), (col_index, row_index), colors.HexColor(fg))]
                table = Table(cells, colWidths=[180] + [min(28, (doc.width-180)/len(column_names))]*len(column_names), repeatRows=1)
                table.setStyle(TableStyle(commands))
                story += [Spacer(1, 6), table]
        if names:
            story += [Spacer(1, 16), p('Clave de managers', 'Heading2')]
            key = Table([[str(ids[name]), p(name, 'Compact')] for name in names], colWidths=[32, doc.width-32])
            key.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#dce3ed'))]))
            story.append(key)
    else:
        outgoing = sorted((item for item in links if item['source'] == manager), key=lambda item: (-int(item['count']), -int(item['value']), item['target']))
        incoming = sorted((item for item in links if item['target'] == manager), key=lambda item: (-int(item['count']), -int(item['value']), item['source']))
        for label, items, name_key in [('Cláusulas realizadas', outgoing, 'target'), ('Cláusulas recibidas', incoming, 'source')]:
            story += [p(label, 'Heading2'), p(f'{sum(int(item["count"]) for item in items)} cláusulas · {money(sum(int(item["value"]) for item in items))}', 'Compact'), Spacer(1, 8)]
            if not items:
                story.append(p('Ninguna.'))
                continue
            rows = [['Manager', 'Cláusulas', 'Importe']] + [[p(item[name_key]), str(item['count']), money(item['value'])] for item in items]
            table = Table(rows, colWidths=[doc.width*.55, doc.width*.16, doc.width*.29], repeatRows=1)
            table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6edf9')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#18316b')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'), ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#dce3ed'))]))
            story += [table, Spacer(1, 12)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


@login_required
@require_GET
def clause_pdf(request):
    from .views import statistics_api
    division = request.GET.get('division', '')
    mode = request.GET.get('mode', 'round')
    kind = request.GET.get('kind', 'heatmap')
    manager = request.GET.get('manager', '') if kind == 'manager' else None
    try:
        number = int(request.GET.get('jornada', '1'))
    except ValueError:
        return JsonResponse({'error': 'Jornada no válida.'}, status=400)
    if not division or mode not in ('general', 'round') or kind not in ('heatmap', 'manager') or not 1 <= number <= 106:
        return JsonResponse({'error': 'Selección no válida.'}, status=400)
    response = statistics_api(request, 2026, number)
    if response.status_code != 200:
        return response
    links = json.loads(response.content)['clause_network']
    if kind == 'manager' and (not manager or not any(manager in (item['source'], item['target']) for item in links)):
        return JsonResponse({'error': 'Selecciona un manager con detalle disponible.'}, status=400)
    period = 'Clasificación general' if mode == 'general' else journey_label(number)
    data = build_clause_pdf(links, division, period, manager)
    response = HttpResponse(data, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="clausulas-' + kind + '.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response
