from django.contrib import admin
from .models import Cart, CartItem
from catalog.admin_utils import jalali_column


# Register your models here.

class CartItemInline(admin.TabularInline):
    added_at_j = jalali_column('added_at', 'تاریخ افزودن')
    model = CartItem
    extra = 0
    can_delete = False
    readonly_fields = ('variant', 'quantity', 'added_at_j')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    updated_at_j = jalali_column('updated_at', 'آخرین تغییر')
    list_select_related = ('user',)
    list_display = ('id', 'user', 'updated_at_j')
    inlines = [CartItemInline]