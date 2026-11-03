from django import template
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils import timezone


CHECKOUT_STEPS = ['سبد خرید', 'اطلاعات ارسال', 'ثبت سفارش', 'پرداخت', 'تأیید سفارش']
_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')

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


@register.filter
def fa_digits(value):
    return str(value).translate(_FA)


@register.filter
def rating_text(value):
    """4.6 -> ۴٫۶"""
    try:
        return f'{float(value):.1f}'.replace('.', '٫').translate(_FA)
    except (TypeError, ValueError):
        return ''


@register.filter
def ago(value):
    """Relative time in Persian: 'همین الان'، '۵ دقیقه پیش'، '۳ روز پیش'."""
    seconds = int((timezone.now() - value).total_seconds())
    if seconds < 60:
        return 'همین الان'
    minutes = seconds // 60
    if minutes < 60:
        text = f'{minutes} دقیقه'
    elif minutes < 1440:
        text = f'{minutes // 60} ساعت'
    else:
        days = minutes // 1440
        if days < 30:
            text = f'{days} روز'
        elif days < 360:
            text = f'{days // 30} ماه'
        else:
            text = f'{max(days // 365, 1)} سال'
    return f'{text} پیش'.translate(_FA)


@register.simple_tag
def stars(value, cls=''):
    """Five stars filled to the given rating (fractions supported)."""
    try:
        rating = max(0.0, min(float(value or 0), 5.0))
    except (TypeError, ValueError):
        rating = 0.0
    return format_html(
        '<span class="stars {}" style="--rate:{}%" role="img" aria-label="امتیاز {} از ۵"></span>',
        cls, round(rating / 5 * 100, 1), rating_text(rating),
    )