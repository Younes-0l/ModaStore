from django.contrib import admin
from .models import WishlistItem


# Register your models here.

@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_at')
    search_fields = ('user__phone_number', 'product__name')
    list_select_related = ('user', 'product')
    raw_id_fields = ('user',)
    autocomplete_fields = ('product',)