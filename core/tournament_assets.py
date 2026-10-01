from pathlib import Path

from django.http import FileResponse, Http404
from django.views.decorators.cache import cache_control


@cache_control(public=True, max_age=86400)
def tournament_logo(request, name):
    if name not in {'jugon-badge', 'jugon-icon', 'copa-rey'}:
        raise Http404
    asset = Path(__file__).parent / 'assets' / 'tournaments' / f'{name}.png'
    return FileResponse(asset.open('rb'), content_type='image/png')
