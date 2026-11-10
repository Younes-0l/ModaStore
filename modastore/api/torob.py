import hmac
import json
import math
from urllib.parse import parse_qs, unquote, urlparse

from django.conf import settings
from django.db.models import Prefetch
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalog.models import ProductImage, ProductVariant

from .utils import absolute_url, product_page_url

PAGE_SIZE = 100
API_VERSION = 'torob_api_v3'
SORTS = {
    'date_added_desc': ('-product__created_at', '-id'),
    'date_updated_desc': ('-updated_at', '-id'),
    'product_id_desc': ('-id',),     # cursor pagination
}


def _authorized(request):
    """Single place to change when Torob gives the real scheme (e.g. signed JWT)."""
    sent = request.headers.get('X-Torob-Token', '')
    return hmac.compare_digest(sent.encode(), settings.TOROB_API_TOKEN.encode())


def _queryset():
    return (
        ProductVariant.objects.filter(is_active=True, product__is_active=True)
        .select_related('product__category')
        .prefetch_related(
            Prefetch('product__images', queryset=ProductImage.objects.all()),   # main image first
            'product__attribute_links__value__attribute',
        )
    )


def _iso(value):
    return timezone.localtime(value).isoformat()


def _item(v):
    p = v.product
    spec = {}
    for link in p.attribute_links.all():
        attr = link.value.attribute
        spec.setdefault(attr.name, []).append(link.value.value)
    spec = {name: '، '.join(values) for name, values in spec.items()}
    if v.color:
        spec['رنگ'] = v.color
    if v.storage:
        spec['حافظه'] = v.storage

    item = {
        'page_unique': str(v.pk),
        'product_group_id': str(p.pk),
        'page_url': product_page_url(p, v),
        'title': ' - '.join(x for x in (p.name, v.color, v.storage) if x),
        'current_price': v.price,                     # Toman
        'availability': v.stock > 0,
        'category_name': p.category.name,
        'image_links': [absolute_url(img.image.url) for img in p.images.all()],
        'spec': spec,
        'date_added': _iso(p.created_at),
        'date_updated': _iso(max(v.updated_at, p.updated_at)),
    }
    if v.old_price:
        item['old_price'] = v.old_price
    return item


def _bad(message, status=400):
    return JsonResponse({'error': message}, status=status)


def _lookup(body):
    """Single product lookup by page_unique or page_url."""
    qs = _queryset()
    if body.get('page_unique'):
        unique = str(body['page_unique'])
        return qs.filter(pk=int(unique)) if unique.isdigit() else qs.none()
    parsed = urlparse(str(body['page_url']))
    vid = parse_qs(parsed.query).get('variant', [''])[0]
    if vid.isdigit():
        return qs.filter(pk=int(vid))
    slug = unquote(parsed.path.rstrip('/').rsplit('/', 1)[-1])
    return qs.filter(product__slug=slug)[:1]


@csrf_exempt            # token-authenticated machine endpoint: no cookies, no CSRF risk
@require_POST
def products_v3(request):
    if not settings.TOROB_API_TOKEN:
        raise Http404                      # disabled until a token is configured
    if not _authorized(request):
        return _bad('unauthorized', 401)

    try:
        body = json.loads(request.body or b'{}')
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        return _bad('invalid JSON body')

    response_headers = {'Cache-Control': 'no-store'}

    # --- lookup mode ---
    if body.get('page_unique') or body.get('page_url'):
        rows = list(_lookup(body))
        if not rows:
            return _bad('product not found', 404)
        return JsonResponse(
            {'api_version': API_VERSION, 'products': [_item(v) for v in rows]},
            headers=response_headers,
        )

    sort = body.get('sort') or 'date_added_desc'
    if sort not in SORTS:
        return _bad('unknown sort')
    qs = _queryset()
    total = qs.count()

    # --- cursor mode ---
    if sort == 'product_id_desc':
        cursor = body.get('cursor')
        if cursor not in (None, ''):
            if not str(cursor).isdigit():
                return _bad('invalid cursor')
            qs = qs.filter(pk__lt=int(cursor))
        rows = list(qs.order_by('-id')[:PAGE_SIZE + 1])
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        return JsonResponse({
            'api_version': API_VERSION, 'total': total,
            'products': [_item(v) for v in rows],
            'next_cursor': str(rows[-1].pk) if more else None,
        }, headers=response_headers)

    # --- page mode ---
    try:
        page = int(body.get('page', 1))
    except (TypeError, ValueError):
        return _bad('invalid page')
    if page < 1:
        return _bad('invalid page')
    start = (page - 1) * PAGE_SIZE
    rows = qs.order_by(*SORTS[sort])[start:start + PAGE_SIZE]
    return JsonResponse({
        'api_version': API_VERSION, 'current_page': page, 'total': total,
        'max_pages': max(1, math.ceil(total / PAGE_SIZE)),
        'products': [_item(v) for v in rows],
    }, headers=response_headers)