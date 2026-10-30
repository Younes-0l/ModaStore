from django.contrib import admin
from .models import Cart, CartItem


# Register your models here.

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    can_delete = False
    readonly_fields = ('variant', 'quantity', 'added_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'updated_at')
    list_select_related = ('user',)
    inlines = [CartItemInline]