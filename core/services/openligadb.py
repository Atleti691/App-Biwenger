import requests


OPENLIGADB_URL = 'https://api.openligadb.de/getmatchdata/{league}/{season}/{round}'
OPENLIGADB_TEAMS_URL = 'https://api.openligadb.de/getavailableteams/{league}/{season}'
ATLETICO_MADRID_LOGO = 'https://assets.laliga.com/assets/2024/06/17/large/cbc5c8cc8c3e8abd0e175c00ee53b723.png'


def get_preferred_team_logo(team_name: str):
    normalized = team_name.casefold().strip()
    if normalized in {'atlético de madrid', 'atletico de madrid', 'atlético', 'atletico'}:
        return ATLETICO_MADRID_LOGO
    return ''


def get_matches(season: int, round_number: int):
    response = requests.get(
        OPENLIGADB_URL.format(league='la1', season=season, round=round_number),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_team_logo(team_name: str, season: int = 2026):
    preferred = get_preferred_team_logo(team_name)
    if preferred:
        return preferred
    try:
        response = requests.get(OPENLIGADB_TEAMS_URL.format(league='la1', season=season), timeout=15)
        response.raise_for_status()
        needle = team_name.casefold().strip()
        for team in response.json():
            names = [team.get('teamName', ''), team.get('shortName', ''), team.get('teamNameShort', '')]
            if any(needle == name.casefold().strip() or needle in name.casefold() for name in names if name):
                return team.get('teamIconUrl', '')
    except requests.RequestException:
        pass
    return ''
