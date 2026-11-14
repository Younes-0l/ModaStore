from django import forms

from accounts.services.validators import normalize_digits, normalize_phone

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # Honeypot: real users never see or fill this field, simple bots do
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'tabindex': '-1', 'autocomplete': 'off',
    }))

    class Meta:
        model = ContactMessage
        fields = ('name', 'phone', 'subject', 'message')
        widgets = {
            'name': forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'مثلاً علی رضایی'}),
            'phone': forms.TextInput(attrs={
                'inputmode': 'tel', 'autocomplete': 'tel', 'dir': 'ltr', 'placeholder': '09123456789',
            }),
            'subject': forms.RadioSelect,
            'message': forms.Textarea(attrs={'rows': 5, 'maxlength': 2000, 'placeholder': 'پیام خود را بنویسید...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # RadioSelect adds a blank choice for fields with a default; drop it
        self.fields['subject'].choices = ContactMessage.Subject.choices
        self.fields['message'].min_length = 10
        self.fields['message'].error_messages['min_length'] = 'پیام باید دست‌کم ۱۰ نویسه باشد.'

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get('phone'))

    def clean_name(self):
        name = ' '.join(normalize_digits(self.cleaned_data.get('name', '')).split())
        if len(name) < 2:
            raise forms.ValidationError('نام را وارد کنید.')
        return name

    def clean_message(self):
        text = self.cleaned_data.get('message', '').strip()
        if len(text) < 10:
            raise forms.ValidationError('پیام باید دست‌کم ۱۰ نویسه باشد.')
        return text

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Spam.')
        return ''
