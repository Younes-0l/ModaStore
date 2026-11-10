import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
TIMEOUT = 15


class GatewayError(Exception):
    """Raised with a user-facing (Persian) message."""


def _api_base():
    return 'https://sandbox.zarinpal.com' if settings.ZARINPAL_SANDBOX else 'https://payment.zarinpal.com'


def _pay_base():
    return 'https://sandbox.zarinpal.com' if settings.ZARINPAL_SANDBOX else 'https://www.zarinpal.com'


def start_url(authority):
    return f'{_pay_base()}/pg/StartPay/{authority}'


def _call(endpoint, payload):
    """POST to ZarinPal v4. Returns (data, errors) as dicts; raises GatewayError if unreachable."""
    if not settings.ZARINPAL_MERCHANT_ID:
        raise GatewayError('درگاه پرداخت پیکربندی نشده است.')
    payload = {'merchant_id': settings.ZARINPAL_MERCHANT_ID, **payload}
    try:
        resp = requests.post(
            f'{_api_base()}/pg/v4/payment/{endpoint}.json',
            json=payload, headers={'Accept': 'application/json'}, timeout=TIMEOUT,
        )
        body = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning('ZarinPal %s call failed: %s', endpoint, exc)
        raise GatewayError('ارتباط با درگاه پرداخت برقرار نشد.') from exc

    data = body.get('data') if isinstance(body, dict) else None
    errors = body.get('errors') if isinstance(body, dict) else None
    # On errors the API returns an empty list instead of an object
    return (data if isinstance(data, dict) else {}), (errors if isinstance(errors, dict) else {})


def request_payment(amount, callback_url, description, mobile, order_number):
    """Create a transaction and return its authority. `amount` is in Toman."""
    data, errors = _call('request', {
        'amount': amount * 10,   # the API works in Rial
        'callback_url': callback_url,
        'description': description,
        'metadata': {'mobile': mobile, 'order_id': order_number},
    })
    if data.get('code') == 100 and data.get('authority'):
        return data['authority']
    logger.error('ZarinPal rejected the request: data=%s errors=%s', data, errors)
    raise GatewayError('ایجاد تراکنش در درگاه ناموفق بود. لطفاً دوباره تلاش کنید.')


def verify(amount, authority):
    """Return (paid, ref_id). 101 means "already verified", which is still a paid order."""
    data, errors = _call('verify', {'amount': amount * 10, 'authority': authority})
    if data.get('code') in (100, 101):
        return True, str(data.get('ref_id', ''))
    if not data and not errors:
        # Unreadable answer: the state is unknown, so do not mark the payment as failed
        raise GatewayError('پاسخ درگاه قابل خواندن نبود.')
    return False, ''