from rest_framework import serializers
from catalog.models import Category, Product, ProductVariant
from .utils import absolute_url, product_page_url


class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.SlugRelatedField(slug_field='slug', read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'parent', 'image')

    def get_image(self, obj) -> str | None:
        return absolute_url(obj.image.url) if obj.image else None


class VariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ('id', 'sku', 'color', 'color_hex', 'storage', 'price', 'old_price',
                  'discount_percent', 'in_stock')


class ProductListSerializer(serializers.ModelSerializer):
    brand = serializers.CharField(source='brand.name')
    category = serializers.CharField(source='category.name')
    min_price = serializers.IntegerField()
    rating_avg = serializers.FloatField()
    image = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ('id', 'name', 'slug', 'brand', 'category', 'image', 'min_price',
                  'rating_avg', 'rating_count', 'url')

    def get_image(self, obj) -> str | None:
        images = obj.img_list
        return absolute_url(images[0].image.url) if images else None

    def get_url(self, obj) -> str:
        return product_page_url(obj)


class ProductDetailSerializer(ProductListSerializer):
    variants = VariantSerializer(many=True, read_only=True)
    images = serializers.SerializerMethodField()
    specs = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ('description', 'variants', 'images', 'specs')

    def get_images(self, obj) -> list[dict]:
        return [
            {'url': absolute_url(i.image.url), 'alt': i.alt, 'is_main': i.is_main}
            for i in obj.img_list
        ]

    def get_specs(self, obj) -> list[dict]:
        return [
            {'group': l.value.attribute.group, 'name': l.value.attribute.name, 'value': l.value.value}
            for l in obj.attribute_links.all()
        ]