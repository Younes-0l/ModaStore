import re

from django.core.exceptions import ValidationError

_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_phone(raw: str) -> str:
    """Convert user input to the canonical 09xxxxxxxxx format or raise."""
    value = (raw or '').translate(_DIGITS)
    value = re.sub(r'[\s\-()]', '', value)
    if value.startswith('+98'):
        value = '0' + value[3:]
    elif value.startswith('0098'):
        value = '0' + value[4:]
    elif value.startswith('98') and len(value) == 12:
        value = '0' + value[2:]
    elif value.startswith('9') and len(value) == 10:
        value = '0' + value
    if not re.fullmatch(r'09\d{9}', value):
        raise ValidationError('شماره موبایل معتبر نیست.')
    return value


def normalize_digits(raw: str) -> str:
    """Convert Persian/Arabic digits to ASCII (used for the OTP input)."""
    return (raw or '').translate(_DIGITS).strip()