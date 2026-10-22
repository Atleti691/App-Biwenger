POSTPONED = {101: (1, 2), 106: (6, 5), 206: (6, 9)}


def journey_label(number):
    if number in (None, ''):
        return 'Jornada sin asignar'
    try:
        number = int(number)
    except (TypeError, ValueError):
        return f'Jornada {number}'
    if number == 206:
        return 'Jornada 6AP2'
    return f'Jornada {POSTPONED[number][0]}AP' if number in POSTPONED else f'Jornada {number}'


def ordered_journeys():
    result = []
    for number in range(1, 39):
        result.append(number)
        result.extend(code for code, (_, after) in POSTPONED.items() if after == number)
    return result
