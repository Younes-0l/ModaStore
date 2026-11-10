from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse


def absolute_url(path):
    """Absolute URL built from SITE_URL, so it is correct behind proxies too."""
    return urljoin(settings.SITE_URL.rstrip('/') + '/', str(path).lstrip('/'))


def product_page_url(product, variant=None):
    url = absolute_url(reverse('catalog:product_detail', args=[product.slug]))
    return f'{url}?variant={variant.pk}' if variant else url