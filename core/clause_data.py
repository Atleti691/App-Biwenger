"""Clause edits and safe compatibility with older jornada clients."""
from copy import deepcopy


def normalize_clauses(items):
    if not isinstance(items, list) or len(items) > 12:
        raise ValueError('Las cláusulas deben ser una lista de hasta 12 elementos.')
    result = []
    for item in items:
        target = item.get('to', item.get('by', '')) if isinstance(item, dict) else ''
        value = item.get('value', 0) if isinstance(item, dict) else item
        if isinstance(value, bool):
            raise ValueError('Importe de cláusula no válido.')
        try:
            amount = int(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('Introduce importes enteros, sin separadores.')
        if amount < 0 or isinstance(value, float) and value != amount:
            raise ValueError('El importe debe ser un entero positivo.')
        if amount:
            if not isinstance(target, str):
                raise ValueError('Manager de destino no válido.')
            result.append({'to': target, 'value': amount})
    return result


def clause_totals(items):
    weighted = sum(item['value'] * (index // 2 + 1) for index, item in enumerate(items))
    return {'money': f'{(weighted + 5) // 10:,}'.replace(',', '.') + ' €',
            'penalty': str(sum((index // 2 + 1) * 2 for index in range(len(items))))}


def merge_journey_data(previous, incoming):
    """An ordinary jornada save may not erase a stored clause list."""
    if not isinstance(incoming, dict) or any(not isinstance(row, dict) for row in incoming.values()):
        raise ValueError('Datos de jornada no válidos.')
    result = deepcopy(previous)
    for name, row in incoming.items():
        merged = {**result.get(name, {}), **row}
        old = previous.get(name, {})
        if 'clauses' not in row or old.get('clauses'):
            # Removal is explicit and scoped through clause_update, never a side effect of saving scores.
            for key in ('clauses', 'money', 'penalty'):
                if key in old:
                    merged[key] = deepcopy(old[key])
        result[name] = merged
    return result


def clause_snapshot(data):
    return {name: {key: deepcopy(row.get(key)) for key in ('clauses', 'money', 'penalty')}
            for name, row in data.items() if row.get('clauses') or row.get('money') or int(row.get('penalty') or 0)}
