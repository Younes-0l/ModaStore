from django.shortcuts import render
from django.views.generic import TemplateView
from django.core.paginator import Paginator
from django.db.models import Count, Max, Min, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView
from .models import Attribute, Brand, Category, Product, ProductImage, ProductVariant


# Create your views here.

class HomeView(TemplateView):
    template_name = 'catalog/home.html'


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