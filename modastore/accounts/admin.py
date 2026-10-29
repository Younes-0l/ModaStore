from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from .models import User, Address, OTPCode


# Register your models here.

class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ('phone_number',)


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    ordering = ('-date_joined',)
    list_display = ('phone_number', 'full_name', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('phone_number', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email')}),
        ('دسترسی‌ها', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('تاریخ‌ها', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'usable_password', 'password1', 'password2'),
        }),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'city', 'is_default')
    search_fields = ('user__phone_number', 'receiver_name', 'postal_code')
    list_select_related = ('user',)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    # Read-only audit log; hashes are not useful to edit
    list_display = ('phone_number', 'created_at', 'attempts', 'is_used')
    search_fields = ('phone_number',)
    readonly_fields = ('phone_number', 'code_hash', 'created_at', 'expires_at', 'attempts', 'is_used')

    def has_add_permission(self, request):
        return False