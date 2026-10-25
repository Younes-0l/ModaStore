from django.contrib import admin
from .models import (
    Attribute, AttributeValue, Brand, Category,
    Product, ProductAttribute, ProductImage, ProductVariant,
)


# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_select_related = ('parent',)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'is_filterable', 'order')
    list_filter = ('is_filterable', 'group')
    search_fields = ('name',)
    filter_horizontal = ('categories',)
    inlines = [AttributeValueInline]


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    # search_fields is required for autocomplete in the product form
    list_display = ('value', 'attribute')
    list_filter = ('attribute',)
    search_fields = ('value', 'attribute__name')
    list_select_related = ('attribute',)


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1
    autocomplete_fields = ('value',)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'is_active', 'created_at')
    list_filter = ('is_active', 'brand', 'category')
    search_fields = ('name', 'variants__sku')
    autocomplete_fields = ('brand', 'category')
    list_select_related = ('brand', 'category')
    inlines = [ProductVariantInline, ProductImageInline, ProductAttributeInline]