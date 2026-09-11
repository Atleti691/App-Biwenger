import requests


OPENLIGADB_URL = 'https://api.openligadb.de/getmatchdata/{league}/{season}/{round}'


def get_matches(season: int, round_number: int):
    response = requests.get(
        OPENLIGADB_URL.format(league='la1', season=season, round=round_number),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()
