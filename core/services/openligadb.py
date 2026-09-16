import requests


OPENLIGADB_URL = 'https://api.openligadb.de/getmatchdata/{league}/{season}/{round}'
OPENLIGADB_TEAMS_URL = 'https://api.openligadb.de/getavailableteams/{league}/{season}'


def get_matches(season: int, round_number: int):
    response = requests.get(
        OPENLIGADB_URL.format(league='la1', season=season, round=round_number),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_team_logo(team_name: str, season: int = 2026):
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
