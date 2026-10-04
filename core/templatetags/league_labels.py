from django import template
from core.journeys import journey_label

register = template.Library()
register.filter('journey_label', journey_label)


@register.filter
def journey_short(number):
    return journey_label(number).replace('Jornada ', 'J', 1)
