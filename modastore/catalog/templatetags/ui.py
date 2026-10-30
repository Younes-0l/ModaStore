from django import template
from django.templatetags.static import static
from django.utils.html import format_html


register = template.Library()

@register.simple_tag
def icon(name, cls=''):
    """Render an SVG from static/svgs/ as a CSS-masked element that inherits the text color."""
    url = static(f'svgs/{name}.svg')
    return format_html(
        '<i class="icon {}" style="--icon:url({})" aria-hidden="true"></i>', cls, url,
    )