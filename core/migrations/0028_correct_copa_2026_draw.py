"""Correct the two audited J8 qualifiers without re-drawing the bracket."""
from django.db import migrations


SEASON = 2026
REPLACEMENTS = (
    ('Segunda División', 'Adrianpt260', 'Rapido de Bouzas', 'Primera RFEF', 'Resalso'),
    ('Segunda RFEF', 'Semela', 'A.A. Ponte Preta', 'Primera RFEF', 'Litoscaboalles'),
)


def correct_draw(apps, schema_editor):
    alias = schema_editor.connection.alias
    Draw = apps.get_model('core', 'CopaReySorteo')
    User = apps.get_model('auth', 'User')
    Audit = apps.get_model('core', 'CambioRegistro')
    Round = apps.get_model('core', 'JornadaRegistro')
    draw = Draw.objects.using(alias).select_for_update().filter(season=SEASON).first()
    if not draw:
        return
    original = draw.participantes
    identities = [(person['division'], person['manager']) for person in original]
    if len(original) != 32 or len(set(identities)) != 32:
        raise RuntimeError('El cuadro de Copa no coincide con el sorteo de 32 participantes verificado.')
    updated, changes = [dict(person) for person in original], []
    for division, outgoing, incoming, opponent_division, opponent in REPLACEMENTS:
        old, new = (division, outgoing), (division, incoming)
        if old not in identities and new in identities:
            continue
        if old not in identities or new in identities:
            raise RuntimeError('La plaza de Copa cambió desde la verificación; revísala antes de sustituirla.')
        index = identities.index(old)
        if original[index].get('guest') or identities[index ^ 1] != (opponent_division, opponent):
            raise RuntimeError('La plaza o su rival no coinciden con el cruce verificado.')
        for target_division, managers in ((division, (outgoing, incoming)), (opponent_division, (opponent,))):
            for record in Round.objects.using(alias).filter(season=SEASON, division=target_division,
                                                            jornada__in=(12, 13), cerrada=True):
                if any(str(record.datos.get(name, {}).get('app') or '').strip()
                       or record.datos.get(name, {}).get('app') == 0 for name in managers):
                    raise RuntimeError('Hay puntos de Copa ya cerrados en un cruce afectado; revisa el cuadro antes de sustituir la plaza.')
        updated[index]['manager'] = incoming
        changes.append({'division': division, 'sale': outgoing, 'entra': incoming,
                        'cruce': index // 2 + 1, 'rival': opponent})
    if not changes:
        return
    actor = User.objects.using(alias).filter(username__iexact='Atleti69').first()
    if not actor:
        raise RuntimeError('No se puede aplicar la corrección sin el registro del superadministrador.')
    Audit.objects.using(alias).create(usuario_id=actor.pk, season=SEASON, jornada=8,
        accion='Corregir plazas del sorteo de Copa del Rey', detalle={
            'origen': 'Corrección autorizada por Rafael el 06/11/2026 tras verificar el corte J8',
            'cambios': changes, 'participantes_antes': original, 'participantes_despues': updated})
    draw.participantes = updated
    draw.save(update_fields=['participantes'], using=alias)


class Migration(migrations.Migration):
    dependencies = [('core', '0027_checo21_permanent_viewer')]
    operations = [migrations.RunPython(correct_draw, migrations.RunPython.noop)]
