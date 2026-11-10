from django.contrib import admin
from .models import WishlistItem
from catalog.admin_utils import jalali_column

# Register your models here.

@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    added_at_j = jalali_column('added_at', 'تاریخ افزودن')   # inside WishlistItemAdmin
    search_fields = ('user__phone_number', 'product__name')
    list_display = ('user', 'product', 'added_at_j')
    list_select_related = ('user', 'product')
    raw_id_fields = ('user',)
    autocomplete_fields = ('product',)