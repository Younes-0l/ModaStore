from django import forms
from django.core.exceptions import ValidationError

from .models import Address, User
from .services.validators import normalize_digits, normalize_phone


class PhoneForm(forms.Form):
    phone_number = forms.CharField(max_length=20)

    def clean_phone_number(self):
        return normalize_phone(self.cleaned_data['phone_number'])


class OTPForm(forms.Form):
    code = forms.CharField(max_length=10)

    def clean_code(self):
        code = normalize_digits(self.cleaned_data['code'])
        if not code.isdigit():
            raise ValidationError('کد باید فقط شامل عدد باشد.')
        return code


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        labels = {'first_name': 'نام', 'last_name': 'نام خانوادگی', 'email': 'ایمیل'}


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            'title', 'receiver_name', 'receiver_phone', 'province',
            'city', 'postal_code', 'full_address', 'is_default',
        )
        widgets = {'full_address': forms.Textarea(attrs={'rows': 3})}

    def clean_receiver_phone(self):
        return normalize_phone(self.cleaned_data['receiver_phone'])

    def clean_postal_code(self):
        return normalize_digits(self.cleaned_data['postal_code'])