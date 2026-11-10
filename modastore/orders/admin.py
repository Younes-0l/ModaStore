from catalog.admin_utils import jalali_column
from .models import Order, OrderItem, Payment
from django.contrib import admin


# Register your models here.

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    created_at_j = jalali_column('created_at', 'تاریخ ایجاد')
    paid_at_j = jalali_column('paid_at', 'تاریخ پرداخت')
    readonly_fields = ('gateway', 'authority', 'amount', 'status', 'ref_id', 'created_at_j', 'paid_at_j')
    exclude = ('created_at', 'paid_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    created_at_j = jalali_column('created_at', 'تاریخ ثبت')
    paid_at_j = jalali_column('paid_at', 'تاریخ پرداخت')
    expires_at_j = jalali_column('expires_at', 'مهلت پرداخت')
    list_display = ('number', 'user', 'status', 'total', 'created_at_j', 'paid_at_j')
    # (list_filter, search_fields, inlines, actions stay as they were)

    def get_readonly_fields(self, request, obj=None):
        swap = {'created_at': 'created_at_j', 'paid_at': 'paid_at_j', 'expires_at': 'expires_at_j'}
        return [swap.get(f.name, f.name) for f in self.model._meta.fields]


class RefundFilter(admin.SimpleListFilter):
    """Opens on the cases that need action."""
    title = 'وضعیت'
    parameter_name = 'st'

    def lookups(self, request, model_admin):
        return [('refund', 'نیاز به بازگشت وجه'), ('all', 'همه')] + list(Payment.Status.choices)

    def queryset(self, request, queryset):
        value = self.value()
        if value is None or value == 'refund':
            return queryset.filter(status=Payment.Status.REFUND_NEEDED)
        return queryset if value == 'all' else queryset.filter(status=value)

    def choices(self, changelist):
        current = self.value() or 'refund'
        for lookup, title in self.lookup_choices:
            yield {
                'selected': current == lookup,
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    created_at_j = jalali_column('created_at', 'تاریخ ایجاد')
    list_display = ('order', 'gateway', 'amount', 'status', 'ref_id', 'created_at_j')
    list_filter = (RefundFilter, 'gateway')
    search_fields = ('order__number', 'ref_id', 'authority')
    list_select_related = ('order',)
    actions = ['mark_refunded']

    def get_readonly_fields(self, request, obj=None):
        return ['order', 'gateway', 'authority', 'amount', 'status', 'ref_id', 'created_at_j', 'paid_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='علامت‌گذاری «بازگشت وجه انجام شد»')
    def mark_refunded(self, request, queryset):
        n = queryset.filter(status=Payment.Status.REFUND_NEEDED).update(status=Payment.Status.REFUNDED)
        self.message_user(request, f'{n} پرداخت بسته شد.')