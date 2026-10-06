import random
from math import floor

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .models import CambioRegistro, CopaReySorteo, JornadaRegistro, UserAccess

ROUNDS = [('Dieciseisavos', (12, 13)), ('Octavos', (14, 15)), ('Cuartos', (16, 17)), ('Semifinales', (18, 19)), ('Final', (36,))]
GUESTS = [('Primera División', 'Raul C'), ('Segunda División', 'Gabrielix de Asturin')]


def latest_records(season):
    records = {}
    for record in JornadaRegistro.objects.filter(season=season).order_by('-updated_at', '-id'):
        records.setdefault((record.division, record.jornada), record)
    return records


def standings(records, roster, through, awards=None):
    from .views import vip_adjustments_for_journey
    positions = {}
    vip_cache = {}
    for division, managers in roster.items():
        totals = {manager: {'total': 0, 'app': 0} for manager in managers}
        for (record_division, journey), record in records.items():
            if record_division != division or not record.cerrada or not (journey <= through or journey in [101, 106] and journey - 100 <= through):
                continue
            if journey not in vip_cache:
                vip_cache[journey] = vip_adjustments_for_journey(journey)
            vip = vip_cache[journey]
            for manager, values in record.datos.items():
                if manager not in totals:
                    continue
                app = int(values.get('app') or 0)
                totals[manager]['app'] += app
                totals[manager]['total'] += app + int(values.get('q') or 0) * 5 + int(values.get('p') or 0) * 10 - int(values.get('penalty') or 0) + vip.get((division, manager), 0)
        for (journey, award_division, manager), points in (awards or {}).items():
            if award_division == division and journey <= through and manager in totals:
                totals[manager]['total'] += points
        ordered = sorted(totals, key=lambda name: (-totals[name]['total'], -totals[name]['app'], name.casefold()))
        for index, name in enumerate(ordered):
            # Equal general scores share a place; alphabetical order never decides a cup tie.
            place = 1 + sum(totals[other]['total'] > totals[name]['total'] for other in ordered)
            positions[(division, name)] = {'position': place, 'order': index, **totals[name]}
    return positions


def participants(records, roster):
    missing = [f'{division} · J{journey}' for division in roster for journey in range(1, 9)
               if not records.get((division, journey)) or not records[(division, journey)].cerrada]
    ranks = standings(records, roster, 8)
    for division, managers in roster.items():
        record = records.get((division, 8))
        if record:
            for manager in managers:
                if record.datos.get(manager, {}).get('app') in (None, ''):
                    missing.append(f'{division} · J8 · faltan puntos APP de {manager}')
    people = []
    for division, managers in roster.items():
        guests = [name for guest_division, name in GUESTS if guest_division == division]
        ordinary = sorted((name for name in managers if name not in guests), key=lambda name: ranks[(division, name)]['order'])[:6]
        people.extend({'division': division, 'manager': name, 'guest': name in guests} for name in guests + ordinary)
    return people, missing


def qualification_outlook(records, roster):
    """A transparent points-gap scenario, not a probability or guaranteed qualification."""
    from .views import vip_adjustments_for_journey
    ranks = standings(records, roster, 8)
    result = []
    for division, names in roster.items():
        if not names:
            continue
        ordered = sorted(names, key=lambda name: ranks[(division, name)]['order'])
        guests = {name for guest_division, name in GUESTS if guest_division == division}
        eligible = [name for name in ordered if name not in guests]
        cutoff = eligible[5] if len(eligible) >= 6 else None
        cutoff_total = ranks[(division, cutoff)]['total'] if cutoff else None
        sample, pending, incomplete = [], [], []
        for number in list(range(1, 9)) + [101, 106]:
            record = records.get((division, number))
            if not record or not record.cerrada:
                if number <= 8:
                    pending.append(number)
                continue
            if any(record.datos.get(name, {}).get('app') in (None, '') for name in names):
                incomplete.append(number)
                continue
            vip = vip_adjustments_for_journey(number)
            total = sum(int(record.datos[name].get('app') or 0)
                        + int(record.datos[name].get('q') or 0) * 5
                        + int(record.datos[name].get('p') or 0) * 10
                        - int(record.datos[name].get('penalty') or 0)
                        + vip.get((division, name), 0) for name in names)
            sample.append({'number': number, 'total': total, 'average': total / len(names)})
        average = sum(row['total'] for row in sample) / (len(names) * len(sample)) if sample else None
        remaining = len(pending)
        reference = average * remaining if average is not None else None
        players = []
        for name in ordered:
            rank = ranks[(division, name)]
            gap = max(0, cutoff_total - rank['total']) if cutoff_total is not None else None
            inside = name in eligible[:6]
            guest = name in guests
            if guest:
                status = 'Invitado: plaza asegurada'
            elif incomplete or cutoff is None:
                status = 'Faltan datos para valorar'
            elif remaining == 0:
                status = 'En plaza al cierre' if inside else 'Fuera de plaza al cierre'
            elif inside:
                status = 'En plaza provisional'
            elif gap == 0:
                status = 'Igualado con el corte'
            elif reference is None or reference <= 0:
                status = 'Sin media positiva de referencia'
            elif gap <= reference:
                status = 'Distancia de hasta una media por jornada pendiente'
            else:
                status = 'Remontada superior a la referencia media'
            players.append({'manager': name, 'position': rank['position'], 'total': rank['total'],
                            'guest': guest, 'inside': inside, 'gap': gap, 'status': status,
                            'reference_percent': gap / reference * 100 if reference and reference > 0 and gap is not None else None,
                            'needed_if_cutoff_average': (floor(cutoff_total - rank['total'] + reference) + 1)
                                if not inside and not guest and cutoff_total is not None and reference is not None and remaining else None})
        result.append({'division': division, 'players': players, 'manager_count': len(names),
                       'sample': sample, 'sample_count': len(sample), 'average': average,
                       'pending': pending, 'remaining': remaining, 'incomplete': incomplete,
                       'cutoff': cutoff, 'cutoff_total': cutoff_total,
                       'cutoff_position': ranks[(division, cutoff)]['position'] if cutoff else None})
    return result


def build_bracket(people, records, roster):
    rounds = []
    current = people
    awards = {}
    for stage_index, (label, journeys) in enumerate(ROUNDS):
        matches, advancing = [], []
        ranks = None
        for index in range(0, len(current), 2):
            pair = current[index:index + 2]
            rows, complete = [], len(pair) == 2 and all(pair)
            for person in pair:
                scores = []
                if person:
                    for journey in journeys:
                        record = records.get((person['division'], journey))
                        value = record.datos.get(person['manager'], {}).get('app') if record else None
                        valid = value is not None and str(value).strip() != ''
                        scores.append({'value': int(value) if valid else None, 'closed': bool(valid and record.cerrada)})
                else:
                    scores = [{'value': None, 'closed': False} for journey in journeys]
                complete = complete and all(score['closed'] for score in scores)
                rows.append({'person': person, 'scores': scores, 'total': sum(score['value'] for score in scores) if all(score['value'] is not None for score in scores) else None})
            winner, reason = None, ''
            if complete:
                if rows[0]['total'] != rows[1]['total']:
                    winner = pair[0 if rows[0]['total'] > rows[1]['total'] else 1]
                else:
                    if ranks is None:
                        ranks = standings(records, roster, journeys[-1], awards)
                    places = [ranks.get((person['division'], person['manager']), {}).get('position') for person in pair]
                    if all(place is not None for place in places) and places[0] != places[1]:
                        winner = pair[0 if places[0] < places[1] else 1]
                        reason = 'Desempate: mejor posición en la general de su división'
                    else:
                        reason = 'Empate también en posición general: pendiente de resolver'
            for row in rows:
                row['winner'] = bool(winner and row['person'] == winner)
                row['prize'] = (50 if row['winner'] else 25) if winner and stage_index == 4 else 15 if row['winner'] else 0
            matches.append({'number': index // 2 + 1, 'rows': rows, 'winner': winner, 'reason': reason, 'complete': complete})
            advancing.append(winner)
        rounds.append({'label': label, 'journeys': journeys, 'matches': matches})
        # Only previous-round prizes affect a later tie; a round never decides itself.
        for match in matches:
            for row in match['rows']:
                if row['prize'] and row['person']:
                    person = row['person']
                    awards[(journeys[-1], person['division'], person['manager'])] = row['prize']
        current = advancing
    return rounds


def cup_awards(season):
    from .views import active_league_managers
    draw = CopaReySorteo.objects.filter(season=season).first()
    if not draw:
        return {}
    roster = active_league_managers(season)
    for person in draw.participantes:
        names = roster.setdefault(person['division'], [])
        if person['manager'] not in names:
            names.append(person['manager'])
    rounds = build_bracket(draw.participantes, latest_records(season), roster)
    awards = {}
    for stage in rounds:
        for match in stage['matches']:
            for row in match['rows']:
                if row['prize']:
                    person = row['person']
                    awards[(stage['journeys'][-1], person['division'], person['manager'])] = row['prize']
    return awards


@login_required
def copa_rey(request):
    from .views import active_league_managers, restore_fixed_staff_access
    season = 2026
    roster = active_league_managers(season)
    records = latest_records(season)
    access, _ = UserAccess.objects.get_or_create(user=request.user)
    access = restore_fixed_staff_access(request.user, access)
    can_draw = request.user.is_superuser or access.role == 'admin'
    people, missing = participants(records, roster)
    ready = not missing and len(people) == 32 and len({(p['division'], p['manager']) for p in people}) == 32
    if request.method == 'POST' and can_draw and ready:
        with transaction.atomic():
            # Serialize concurrent clicks on the same administrator's account.
            UserAccess.objects.select_for_update().get(pk=access.pk)
            random.SystemRandom().shuffle(people)
            draw, created = CopaReySorteo.objects.get_or_create(season=season, defaults={'participantes': people, 'creado_por': request.user})
            if created:
                CambioRegistro.objects.create(usuario=request.user, jornada=8, accion='Sorteo Copa del Rey', detalle={'season': season, 'participantes': people})
        return redirect('copa_rey')
    draw = CopaReySorteo.objects.filter(season=season).first()
    if draw:
        for person in draw.participantes:
            names = roster.setdefault(person['division'], [])
            if person['manager'] not in names:
                names.append(person['manager'])
    return render(request, 'copa_rey.html', {'draw': draw, 'rounds': build_bracket(draw.participantes, records, roster) if draw else [], 'people': people, 'missing': missing, 'ready': ready, 'can_draw': can_draw,
                                          'qualification_outlook': qualification_outlook(records, roster)})
