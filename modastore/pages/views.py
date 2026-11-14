from django.shortcuts import render, redirect
from datetime import timedelta
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from catalog.models import Category, Product
from .models import ContactMessage
from .forms import ContactForm


# Create your views here.

SESSION_KEY = 'contact_sent'
MAX_PER_HOUR = 5

# Iranian week: Saturday=0 ... Friday=6 (Python's weekday(): Monday=0)
# Open Saturday-Wednesday 09-18, Thursday 09-14, closed Friday
HOURS = {5: (9, 18), 6: (9, 18), 0: (9, 18), 1: (9, 18), 2: (9, 18), 3: (9, 14)}


def _client_ip(request):
    return request.META.get('REMOTE_ADDR') or None


def _is_open_now():
    now = timezone.localtime()
    hours = HOURS.get(now.weekday())
    return bool(hours and hours[0] <= now.hour < hours[1])


@require_http_methods(['GET', 'POST'])
def contact(request):
    ip = _client_ip(request)
    form = ContactForm(request.POST or None, initial={'subject': ContactMessage.Subject.ORDER})
    limited = False

    if request.method == 'POST':
        since = timezone.now() - timedelta(hours=1)
        recent = ContactMessage.objects.filter(created_at__gte=since)
        recent = recent.filter(user=request.user) if request.user.is_authenticated else recent.filter(ip=ip)
        limited = recent.count() >= MAX_PER_HOUR
        if not limited and form.is_valid():
            msg = form.save(commit=False)
            msg.ip = ip
            if request.user.is_authenticated:
                msg.user = request.user
            msg.save()
            request.session[SESSION_KEY] = True
            return redirect('pages:contact')   # PRG: a refresh must not resend the message

    if request.method == 'GET' and request.user.is_authenticated and not form.is_bound:
        form.initial.update({'name': request.user.full_name, 'phone': request.user.phone_number})

    return render(request, 'pages/contact.html', {
        'form': form,
        'limited': limited,
        'sent': request.session.pop(SESSION_KEY, False),
        'is_open': _is_open_now(),
    })


def not_found(request, exception=None):
    """Custom 404: keep the visitor in the shop with search, categories and live suggestions."""
    suggestions = []
    categories = []
    try:
        categories = list(Category.objects.filter(is_active=True, parent=None)[:6])
        products = (
            Product.objects.filter(is_active=True, variants__is_active=True)
            .select_related('brand')
            .prefetch_related('variants', 'images')
            .distinct().order_by('-created_at')[:4]
        )
        for p in products:
            variants = sorted((v for v in p.variants.all() if v.is_active), key=lambda v: v.price)
            if not variants:
                continue
            main = next((i for i in p.images.all() if i.is_main), None)
            suggestions.append({
                'name': p.name, 'slug': p.slug, 'brand': p.brand.name if p.brand_id else '',
                'image': main.image.url if main else '',
                'price': variants[0].price, 'old_price': variants[0].old_price,
            })
    except Exception:   # a 404 page must never fail because of the database
        suggestions, categories = [], []
    return TemplateResponse(request, '404.html', {
        'suggestions': suggestions, 'categories': categories,
    }, status=404).render()