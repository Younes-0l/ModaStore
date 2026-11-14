from django.contrib import admin
from catalog.admin_utils import jalali_column
from .models import ContactMessage


# Register your models here.

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'subject', 'short_message', 'created_at_j', 'is_handled')
    list_filter = ('is_handled', 'subject')
    list_editable = ('is_handled',)
    search_fields = ('name', 'phone', 'message')
    readonly_fields = ('user', 'name', 'phone', 'subject', 'message', 'ip', 'created_at_j')
    fields = ('name', 'phone', 'subject', 'message', 'user', 'ip', 'created_at_j', 'is_handled')
    actions = ('mark_handled',)

    created_at_j = jalali_column('created_at', 'تاریخ ارسال')

    @admin.display(description='پیام')
    def short_message(self, obj):
        return obj.message[:70] + ('…' if len(obj.message) > 70 else '')

    def has_add_permission(self, request):
        return False

    @admin.action(description='علامت‌گذاری به‌عنوان بررسی‌شده')
    def mark_handled(self, request, queryset):
        self.message_user(request, f'{queryset.update(is_handled=True)} پیام بررسی شد.')
