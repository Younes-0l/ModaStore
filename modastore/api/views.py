from django.shortcuts import render
from django.db.models import Exists, Min, OuterRef, Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from catalog.models import Category, Product, ProductImage, ProductVariant
from .serializers import CategorySerializer, ProductDetailSerializer, ProductListSerializer


# Create your views here.

ORDERINGS = {
    'newest': '-created_at', 'cheapest': 'min_price',
    'expensive': '-min_price', 'rating': '-rating_avg',
}


@extend_schema_view(list=extend_schema(parameters=[
    OpenApiParameter('category', str, description='Category slug (includes its sub-categories)'),
    OpenApiParameter('brand', str, description='Brand slug'),
    OpenApiParameter('q', str, description='Search in product and brand names'),
    OpenApiParameter('in_stock', str, enum=['1'], description='Only products with an in-stock variant'),
    OpenApiParameter('ordering', str, enum=list(ORDERINGS), description='Default: newest'),
]))
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == 'retrieve' else ProductListSerializer

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True)
            .select_related('brand', 'category')
            .prefetch_related(
                Prefetch('variants', queryset=ProductVariant.objects.filter(is_active=True)),
                Prefetch('images', queryset=ProductImage.objects.all(), to_attr='img_list'),
                'attribute_links__value__attribute',
            )
            .annotate(min_price=Min('variants__price', filter=Q(variants__is_active=True)))
            .filter(min_price__isnull=False)
        )
        if self.action != 'list':
            return qs

        params = self.request.query_params
        if category := params.get('category'):
            qs = qs.filter(Q(category__slug=category) | Q(category__parent__slug=category))
        if brand := params.get('brand'):
            qs = qs.filter(brand__slug=brand)
        if q := params.get('q', '').strip():
            qs = qs.filter(Q(name__icontains=q) | Q(brand__name__icontains=q))
        if params.get('in_stock') == '1':
            qs = qs.filter(Exists(ProductVariant.objects.filter(
                product_id=OuterRef('pk'), is_active=True, stock__gt=0,
            )))
        return qs.order_by(ORDERINGS.get(params.get('ordering'), '-created_at'), '-id')


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.filter(is_active=True).select_related('parent')
    lookup_field = 'slug'
    pagination_class = None