from django import template
from django.templatetags.static import static
from django.utils.html import format_html


CHECKOUT_STEPS = ['سبد خرید', 'اطلاعات ارسال', 'ثبت سفارش', 'پرداخت', 'تأیید سفارش']
register = template.Library()

@register.simple_tag
def icon(name, cls=''):
    """Render an SVG from static/svgs/ as a CSS-masked element that inherits the text color."""
    url = static(f'svgs/{name}.svg')
    return format_html(
        '<i class="icon {}" style="--icon:url({})" aria-hidden="true"></i>', cls, url,
    )

@register.inclusion_tag('partials/checkout_steps.html')
def checkout_steps(current):
    """current=1..5 marks the active step; 6 marks every step as done."""
    steps = []
    for n, label in enumerate(CHECKOUT_STEPS, start=1):
        state = 'done' if n < current else 'current' if n == current else 'todo'
        steps.append({'n': n, 'label': label, 'state': state})
    return {'steps': steps}