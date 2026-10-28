from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Count, Max, Min, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView
from .models import Attribute, Brand, Category, Product, ProductImage, ProductVariant
import json


# Create your views here.

class HomeView(TemplateView):
    template_name = 'catalog/home.html'

    @staticmethod
    def _with_card_data(qs):
        """Attach everything product_card.html needs, in a fixed number of queries."""
        return qs.select_related('brand').prefetch_related(
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.filter(is_active=True),
            ),
            Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_main=True),
                to_attr='main_images',
            ),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Only products that can actually be bought (at least one active variant)
        purchasable = Product.objects.filter(
            is_active=True, variants__is_active=True,
        )

        ctx['categories'] = Category.objects.filter(is_active=True, parent=None)[:6]
        ctx['new_products'] = self._with_card_data(
            purchasable.distinct().order_by('-created_at')
        )[:8]
        ctx['offer_products'] = self._with_card_data(
            purchasable.filter(variants__old_price__isnull=False)
            .distinct().order_by('-updated_at')
        )[:8]
        ctx['brands'] = Brand.objects.filter(is_active=True).exclude(logo='')[:8]
        return ctx


class ProductListView(ListView):
    """Product listing with filters, sorting and pagination."""

    model = Product
    template_name = 'catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    SORT_OPTIONS = {
        'newest': ('جدیدترین', '-created_at'),
        'cheapest': ('ارزان‌ترین', 'min_price'),
        'expensive': ('گران‌ترین', '-min_price'),
    }

    def get_queryset(self):
        params = self.request.GET

        qs = (
            Product.objects.filter(is_active=True)
            .select_related('brand', 'category')
            .prefetch_related(
                Prefetch(
                    'variants',
                    queryset=ProductVariant.objects.filter(is_active=True),
                ),
                Prefetch(
                    'images',
                    queryset=ProductImage.objects.filter(is_main=True),
                    to_attr='main_images',
                ),
            )
            .annotate(
                min_price=Min('variants__price', filter=Q(variants__is_active=True)),
            )
            # Products without any active variant are not purchasable yet
            .filter(min_price__isnull=False)
        )

        # Category filter (includes direct children)
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            self.category = get_object_or_404(Category, slug=category_slug, is_active=True)
            qs = qs.filter(Q(category=self.category) | Q(category__parent=self.category))
        else:
            self.category = None

        # Search
        q = params.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(brand__name__icontains=q))

        # Brands (multiple)
        brands = params.getlist('brand')
        if brands:
            qs = qs.filter(brand__slug__in=brands)

        # Price range
        price_min = self._to_int(params.get('price_min'))
        price_max = self._to_int(params.get('price_max'))
        if price_min is not None:
            qs = qs.filter(variants__price__gte=price_min, variants__is_active=True)
        if price_max is not None:
            qs = qs.filter(variants__price__lte=price_max, variants__is_active=True)

        # In-stock only
        if params.get('in_stock') == '1':
            qs = qs.filter(variants__stock__gt=0, variants__is_active=True)

        # Dynamic attribute filters: attr_<attribute-slug>=<value-id>
        for key in params:
            if key.startswith('attr_'):
                ids = [v for v in params.getlist(key) if v.isdigit()]
                if ids:
                    qs = qs.filter(attribute_values__id__in=ids)

        # Joins above can duplicate rows
        qs = qs.distinct()

        sort = params.get('sort', 'newest')
        if sort not in self.SORT_OPTIONS:
            sort = 'newest'
        return qs.order_by(self.SORT_OPTIONS[sort][1], '-id')

    @staticmethod
    def _to_int(value):
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET

        # Brands for the sidebar
        ctx['brands'] = Brand.objects.filter(is_active=True)
        ctx['selected_brands'] = params.getlist('brand')

        # Filterable attributes (limited to the current category when set)
        attrs = Attribute.objects.filter(is_filterable=True).prefetch_related('values')
        if self.category:
            attrs = attrs.filter(categories=self.category)
        ctx['filter_attributes'] = attrs.distinct()
        selected_attr_ids = set()
        for key in params:
            if key.startswith('attr_'):
                selected_attr_ids.update(
                    int(v) for v in params.getlist(key) if v.isdigit()
                )
        ctx['selected_attr_ids'] = selected_attr_ids

        ctx['categories'] = Category.objects.filter(is_active=True, parent=None)
        ctx['current_category'] = self.category
        ctx['sort_options'] = [(k, v[0]) for k, v in self.SORT_OPTIONS.items()]
        ctx['current_sort'] = params.get('sort', 'newest')
        ctx['q'] = params.get('q', '')
        ctx['price_min'] = params.get('price_min', '')
        ctx['price_max'] = params.get('price_max', '')
        ctx['in_stock'] = params.get('in_stock') == '1'

        # Keep filters in pagination links (everything except "page")
        sort_query = params.copy()
        sort_query.pop('page', None)
        sort_query.pop('sort', None)
        ctx['sort_query_string'] = sort_query.urlencode()
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = 'catalog/product_detail.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related('brand', 'category')
            .prefetch_related(
                Prefetch(
                    'variants',
                    queryset=ProductVariant.objects.filter(is_active=True),
                ),
                'images',
                'attribute_links__value__attribute',
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object
        variants = list(product.variants.all())  # already prefetched, ordered by price

        # Default selection: cheapest in-stock variant, else the first one
        default = next((v for v in variants if v.in_stock), variants[0] if variants else None)

        ctx['variants'] = variants
        ctx['default_variant'] = default
        ctx['variants_json'] = [
            {
                'id': v.id,
                'color': v.color,
                'storage': v.storage,
                'price': v.price,
                'old_price': v.old_price,
                'discount': v.discount_percent,
                'stock': v.stock,
            }
            for v in variants
        ]
        # Distinct options in order of appearance
        ctx['colors'] = list({v.color: v.color_hex for v in variants if v.color}.items())
        ctx['storages'] = list(dict.fromkeys(v.storage for v in variants if v.storage))

        # Specs grouped by attribute group
        specs = {}
        for link in product.attribute_links.all():
            attr = link.value.attribute
            specs.setdefault(attr.group or 'سایر', []).append((attr.name, link.value.value))
        ctx['spec_groups'] = specs

        ctx['related_products'] = (
            Product.objects.filter(is_active=True, category=product.category)
            .exclude(pk=product.pk)
            .select_related('brand')
            .prefetch_related(
                Prefetch('variants', queryset=ProductVariant.objects.filter(is_active=True)),
                Prefetch('images', queryset=ProductImage.objects.filter(is_main=True), to_attr='main_images'),
            )[:4]
        )
        return ctx