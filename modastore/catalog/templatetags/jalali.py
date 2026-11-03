import datetime as dt

import jdatetime
from django import template
from django.utils import timezone

register = template.Library()

_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
_MONTHS = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]


def _to_jalali(value):
    """Convert a date/datetime to jdatetime, using Tehran time for aware datetimes."""
    if not value:
        return None
    if isinstance(value, dt.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)   # UTC -> TIME_ZONE (Asia/Tehran)
        return jdatetime.datetime.fromgregorian(datetime=value)
    if isinstance(value, dt.date):
        return jdatetime.date.fromgregorian(date=value)
    return None


@register.filter
def jdate(value):
    """12 آبان ۱۴۰۵"""
    j = _to_jalali(value)
    if j is None:
        return ''
    return f'{j.day} {_MONTHS[j.month - 1]} {j.year}'.translate(_FA)


@register.filter
def jdate_num(value):
    """۱۴۰۵/۰۸/۱۲"""
    j = _to_jalali(value)
    if j is None:
        return ''
    return f'{j.year:04d}/{j.month:02d}/{j.day:02d}'.translate(_FA)


@register.filter
def jdatetime_num(value):
    """۱۴۰۵/۰۸/۱۲ - ۱۴:۳۵"""
    j = _to_jalali(value)
    if j is None:
        return ''
    if not isinstance(j, jdatetime.datetime):
        return jdate_num(value)
    return f'{j.year:04d}/{j.month:02d}/{j.day:02d} - {j.hour:02d}:{j.minute:02d}'.translate(_FA)