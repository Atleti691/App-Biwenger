"""Confirmed qualification rules. Undecided formats never produce winners."""
from .cup import cup_awards, latest_records, standings


def ordered_ranking(records, roster, division, through, awards=None):
    ranks = standings(records, roster, through, awards)
    return sorted(
        ({'manager': name, **ranks[(division, name)]} for name in roster.get(division, [])),
        key=lambda row: row['order'],
    )


def complete(records, division, journeys, managers):
    return all(
        records.get((division, journey)) and records[(division, journey)].cerrada
        and all(records[(division, journey)].datos.get(name, {}).get('app') not in (None, '') for name in managers)
        for journey in journeys
    )


def qualification(records, roster, division, through, awards=None):
    rows = ordered_ranking(records, roster, division, through, awards)
    ready = complete(records, division, range(1, through + 1), roster.get(division, []))
    # Do not let alphabetical order decide a tied qualification boundary.
    tie = len(rows) > 6 and rows[5]['total'] == rows[6]['total'] and rows[5]['app'] == rows[6]['app']
    tie = tie or len(rows) > 8 and rows[7]['total'] == rows[8]['total'] and rows[7]['app'] == rows[8]['app']
    return rows, ready and len(rows) >= 8 and not tie


def net_match(records, roster, division, managers, journeys, awards=None, cache=None, tie_break=True, metric='app'):
    if len(managers) != 2 or not complete(records, division, journeys, managers):
        return {'managers': managers, 'scores': [], 'winner': None, 'reason': 'Pendiente de datos cerrados'}
    cache = {} if cache is None else cache
    for journey in (journeys[0] - 1, journeys[-1]):
        if journey not in cache:
            cache[journey] = standings(records, roster, journey, awards)
    before = cache[journeys[0] - 1]
    after = cache[journeys[-1]]
    scores = [sum(int(records[(division, journey)].datos[name]['app']) for journey in journeys)
              if metric == 'app' else after[(division, name)]['total'] - before[(division, name)]['total']
              for name in managers]
    winner = None
    reason = 'Puntos APP' if metric == 'app' else 'Total neto'
    if scores[0] != scores[1]:
        winner = managers[0 if scores[0] > scores[1] else 1]
    elif tie_break:
        positions = [after[(division, name)]['position'] for name in managers]
        reason = 'Desempate por clasificación general'
        if positions[0] != positions[1]:
            winner = managers[0 if positions[0] < positions[1] else 1]
        else:
            reason = 'Empate también en la general: pendiente de resolver'
    else:
        reason = 'Empate en puntos APP' if metric == 'app' else 'Empate en total neto'
    return {'managers': managers, 'scores': scores, 'winner': winner, 'reason': reason}


def round_robin(managers):
    """Natural seeding, each pair once and one bye per manager for seven entrants."""
    slots = list(managers)
    if len(slots) % 2:
        slots.append(None)
    rounds = []
    for journey in range(26, 26 + len(slots) - 1):
        pairs = [(slots[i], slots[-1-i]) for i in range(len(slots)//2)]
        rounds.append({'journey': journey, 'pairs': [pair for pair in pairs if None not in pair],
                       'bye': next((a or b for a, b in pairs if None in (a, b)), None)})
        slots = [slots[0], slots[-1], *slots[1:-1]]
    return rounds


def title_competition(records, roster, division, awards=None, cache=None):
    cache = {} if cache is None else cache
    rows, ready = qualification(records, roster, division, 24, awards)
    playin = net_match(records, roster, division, [row['manager'] for row in rows[6:8]], (25,), awards, cache) if ready else {'managers': [row['manager'] for row in rows[6:8]], 'scores': [], 'winner': None, 'reason': 'Clasificación J24 provisional o empate en el corte'}
    qualified = [row['manager'] for row in rows[:6]] if ready else []
    if playin['winner']:
        qualified.append(playin['winner'])
    groups = round_robin(qualified) if len(qualified) == 7 else []
    for stage in groups:
        stage['matches'] = [net_match(records, roster, division, list(pair), (stage['journey'],), awards, cache, tie_break=False, metric='app')
                            for pair in stage.pop('pairs')]
    table = {name: {'manager': name, 'played': 0, 'won': 0, 'drawn': 0, 'lost': 0, 'points': 0, 'app': 0}
             for name in qualified}
    for stage in groups:
        for match in stage['matches']:
            if not match['scores']:
                continue
            for index, name in enumerate(match['managers']):
                row = table[name]
                score, rival = match['scores'][index], match['scores'][1-index]
                row['played'] += 1
                row['app'] += score
                row['won'] += score > rival
                row['drawn'] += score == rival
                row['lost'] += score < rival
                row['points'] += 3 if score > rival else 1 if score == rival else 0
    ranks = standings(records, roster, 32, awards)
    group_table = sorted(table.values(), key=lambda row: (-row['points'], ranks[(division, row['manager'])]['position'], row['manager'].casefold()))
    groups_ready = len(qualified) == 7 and complete(records, division, range(26, 33), qualified)
    for left, right in zip(group_table[:4], group_table[1:5]):
        if left['points'] == right['points'] and ranks[(division, left['manager'])]['position'] == ranks[(division, right['manager'])]['position']:
            groups_ready = False
    final_four = []
    if groups_ready:
        for a, b in [(0, 3), (1, 2)]:
            final_four.append(net_match(records, roster, division, [group_table[a]['manager'], group_table[b]['manager']], (34, 35), awards, cache))
    winners = [match['winner'] for match in final_four if match['winner']]
    losers = [next(name for name in match['managers'] if name != match['winner']) for match in final_four if match['winner']]
    final = net_match(records, roster, division, winners, (36,), awards, cache)
    third = net_match(records, roster, division, losers, (36,), awards, cache)
    runner_up = next((name for name in final['managers'] if name != final['winner']), None) if final['winner'] else None
    return {'rows': rows, 'ready': ready, 'playin': playin, 'qualified': qualified, 'groups': groups,
            'group_table': group_table, 'groups_ready': groups_ready, 'final_four': final_four,
            'title_final': final, 'third_place': third, 'champion': final['winner'], 'runner_up': runner_up}


def promotion_place(champion, runner_up, ranking, direct):
    if not champion or not runner_up:
        return None
    for name in [champion, runner_up, *[row['manager'] for row in ranking]]:
        if name not in direct:
            return name
    return None


def promotion_competition(records, roster, title, awards=None, cache=None):
    cache = {} if cache is None else cache
    division = 'Segunda División'
    second = ordered_ranking(records, roster, division, 35, awards)
    direct_rows = ordered_ranking(records, roster, division, 36, awards)
    direct_ready = bool(roster.get(division)) and complete(records, division, range(1, 37), roster.get(division, []))
    # An exact tie at the direct-promotion cutoff needs a decision, not alphabetic ordering.
    if len(direct_rows) > 2 and (direct_rows[1]['total'], direct_rows[1]['app']) == (direct_rows[2]['total'], direct_rows[2]['app']):
        direct_ready = False
    direct = [row['manager'] for row in direct_rows[:2]]
    title_promoted = promotion_place(title['champion'], title['runner_up'], direct_rows, direct) if direct_ready else None
    candidates = [row for row in second[2:] if row['manager'] not in {*direct, title_promoted}][:4]
    promotion_ready = bool(title_promoted) and direct_ready and len(candidates) == 4
    if any((left['total'], left['app']) == (right['total'], right['app']) for left, right in zip(second[2:], second[3:])):
        promotion_ready = False
    semifinals = []
    for a, b in [(0, 3), (1, 2)]:
        names = [candidates[index]['manager'] for index in (a, b) if index < len(candidates)]
        semifinals.append(net_match(records, roster, division, names, (36,), awards, cache) if promotion_ready else {'managers': names, 'scores': [], 'winner': None, 'reason': 'Cruce provisional hasta cerrar J35 y confirmar los ascensos de J36'})
    winners = [match['winner'] for match in semifinals if match['winner']]
    final = net_match(records, roster, division, winners, (37,), awards, cache)
    promoted = direct + [title_promoted, final['winner']] if direct_ready and title_promoted and final['winner'] else []
    return {'semifinals': semifinals, 'promotion_final': final, 'direct': direct_rows[:2],
            'direct_ready': direct_ready, 'title_promoted': title_promoted, 'promoted': promoted}


def playoff_data(season, division):
    from .views import active_league_managers
    records = latest_records(season)
    roster = active_league_managers(season)
    awards = cup_awards(season)
    cache = {}
    title = title_competition(records, roster, division, awards, cache)
    second_title = title if division == 'Segunda División' else title_competition(records, roster, 'Segunda División', awards, cache)
    return {**title, **promotion_competition(records, roster, second_title, awards, cache)}
