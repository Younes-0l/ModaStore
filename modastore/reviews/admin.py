from django.contrib import admin
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import Truncator
from .models import Review
from .services import services


# Register your models here.

class StatusFilter(admin.SimpleListFilter):
    """Defaults to the pending queue, so admins land directly on what needs review."""

    title = 'وضعیت'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('pending', 'در انتظار تأیید'), ('approved', 'تأیید شده'),
            ('rejected', 'رد شده'), ('all', 'همه'),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            return queryset.filter(status=Review.Status.PENDING)
        return queryset if value == 'all' else queryset.filter(status=value)

    def choices(self, changelist):
        current = self.value() or 'pending'
        for lookup, title in self.lookup_choices:
            yield {
                'selected': current == lookup,
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('status_badge', 'stars', 'excerpt', 'product', 'reviewer', 'is_verified_buyer', 'created_at')
    list_display_links = ('excerpt',)
    list_filter = (StatusFilter, 'is_verified_buyer', 'rating')
    search_fields = ('body', 'title', 'product__name', 'user__phone_number')
    list_select_related = ('product', 'user')
    list_per_page = 50
    actions = ['approve', 'reject']
    actions_on_top = True
    readonly_fields = (
        'product', 'user', 'rating', 'is_verified_buyer', 'purchased_variant',
        'helpful_count', 'created_at', 'moderated_at', 'moderated_by',
    )
    fieldsets = (
        ('وضعیت', {'fields': ('status', 'store_reply')}),
        ('نظر', {'fields': ('product', 'user', 'rating', 'recommend', 'title', 'body', 'pros', 'cons')}),
        ('اطلاعات', {'fields': ('is_verified_buyer', 'purchased_variant', 'helpful_count', 'created_at', 'moderated_at', 'moderated_by')}),
    )

    # ----- list columns -----
    @admin.display(description='وضعیت', ordering='status')
    def status_badge(self, obj):
        colors = {'pending': '#c2410c', 'approved': '#166534', 'rejected': '#991b1b'}
        return format_html(
            '<b style="color:{}">{}</b>', colors[obj.status], obj.get_status_display(),
        )

    @admin.display(description='امتیاز', ordering='rating')
    def stars(self, obj):
        return format_html('<span style="color:#f59e0b;letter-spacing:1px">{}</span>{}', '★' * obj.rating, '☆' * (5 - obj.rating))

    @admin.display(description='متن نظر')
    def excerpt(self, obj):
        return Truncator(obj.body).chars(80)

    @admin.display(description='کاربر', ordering='user__phone_number')
    def reviewer(self, obj):
        return obj.user.phone_number

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        pending = Review.objects.filter(status=Review.Status.PENDING).count()
        extra_context = {**(extra_context or {}), 'title': f'نظرات ({pending} نظر در انتظار بررسی)'}
        return super().changelist_view(request, extra_context)

    # ----- bulk actions -----
    def _moderate(self, request, queryset, status):
        product_ids = list(queryset.order_by().values_list('product_id', flat=True).distinct())
        n = queryset.exclude(status=status).update(
            status=status, moderated_at=timezone.now(), moderated_by=request.user,
        )
        for pid in product_ids:      # update() skips signals, so refresh ratings explicitly
            services.recalculate(pid)
        return n

    @admin.action(description='✓ تأیید نظرهای انتخاب‌شده')
    def approve(self, request, queryset):
        n = self._moderate(request, queryset, Review.Status.APPROVED)
        self.message_user(request, f'{n} نظر تأیید شد.')

    @admin.action(description='✕ رد نظرهای انتخاب‌شده')
    def reject(self, request, queryset):
        n = self._moderate(request, queryset, Review.Status.REJECTED)
        self.message_user(request, f'{n} نظر رد شد.')

    # ----- single review -----
    def save_model(self, request, obj, form, change):
        now = timezone.now()
        if 'status' in form.changed_data:
            obj.moderated_at, obj.moderated_by = now, request.user
        if 'store_reply' in form.changed_data:
            obj.replied_at = now if obj.store_reply.strip() else None
        super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        """"Approve and next" / "Reject and next": review the whole queue with one click each."""
        approve, reject = '_approve_next' in request.POST, '_reject_next' in request.POST
        if not (approve or reject):
            return super().response_change(request, obj)

        obj.status = Review.Status.APPROVED if approve else Review.Status.REJECTED
        obj.moderated_at, obj.moderated_by = timezone.now(), request.user
        obj.save()
        self.message_user(request, 'نظر تأیید شد.' if approve else 'نظر رد شد.', messages.SUCCESS)

        nxt = Review.objects.filter(status=Review.Status.PENDING).exclude(pk=obj.pk).order_by('created_at').first()
        if nxt:
            return redirect(reverse('admin:reviews_review_change', args=[nxt.pk]))
        self.message_user(request, 'همه نظرها بررسی شد. 🎉', messages.INFO)
        return redirect(reverse('admin:reviews_review_changelist'))