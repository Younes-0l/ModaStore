from django import template
from django.contrib.humanize.templatetags.humanize import intcomma


register = template.Library()

@register.filter
def price_format(value):
    if value is None:
        return '0'

    return intcomma(value, use_l10n=False)