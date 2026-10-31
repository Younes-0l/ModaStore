from django.contrib import admin
from .services import services
from .models import Order, OrderItem, Payment

# Register your models here.

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ('product_name', 'sku', 'color', 'storage', 'unit_price', 'quantity')
    exclude = ('variant', 'image_name')

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = ('authority', 'amount', 'status', 'ref_id', 'created_at', 'paid_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'user', 'status', 'total', 'created_at', 'paid_at')
    list_filter = ('status', 'created_at')
    search_fields = ('number', 'user__phone_number', 'receiver_name', 'receiver_phone')
    list_select_related = ('user',)
    inlines = [OrderItemInline, PaymentInline]
    actions = ['mark_shipped', 'mark_delivered', 'cancel_unpaid']

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='علامت‌گذاری به‌عنوان «ارسال شده»')
    def mark_shipped(self, request, queryset):
        n = queryset.filter(status=Order.Status.PROCESSING).update(status=Order.Status.SHIPPED)
        self.message_user(request, f'{n} سفارش بروزرسانی شد.')

    @admin.action(description='علامت‌گذاری به‌عنوان «تحویل داده شده»')
    def mark_delivered(self, request, queryset):
        n = queryset.filter(status=Order.Status.SHIPPED).update(status=Order.Status.DELIVERED)
        self.message_user(request, f'{n} سفارش بروزرسانی شد.')

    @admin.action(description='لغو سفارش‌های پرداخت‌نشده و بازگرداندن موجودی')
    def cancel_unpaid(self, request, queryset):
        n = sum(1 for pk in queryset.values_list('pk', flat=True) if services.cancel_order(pk))
        self.message_user(request, f'{n} سفارش لغو شد.')