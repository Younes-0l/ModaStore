import re
from django import forms
from django.core.exceptions import ValidationError
from accounts.services.validators import normalize_digits
from .models import Review

LINK_RE = re.compile(r'(https?://|www\.|t\.me/|@\w{3,}|\b\w+\.(com|ir|net|org|info)\b)', re.I)
PHONE_RE = re.compile(r'(?<!\d)(?:\+?98|0)?9\d{9}(?!\d)')


def _reject_contact_info(text):
    plain = re.sub(r'[\s\-]', '', normalize_digits(text))
    if LINK_RE.search(text) or PHONE_RE.search(plain):
        raise ValidationError('لطفاً از درج لینک، آیدی یا شماره تماس خودداری کنید.')


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, i) for i in (5, 4, 3, 2, 1)], coerce=int,
        widget=forms.RadioSelect,
        error_messages={'required': 'لطفاً امتیاز خود را مشخص کنید.'},
    )
    recommend = forms.ChoiceField(
        choices=[('1', 'پیشنهاد می‌کنم'), ('0', 'پیشنهاد نمی‌کنم')],
        required=False, widget=forms.RadioSelect,
    )

    class Meta:
        model = Review
        fields = ('rating', 'title', 'body', 'pros', 'cons', 'recommend')
        labels = {
            'title': 'عنوان نظر (اختیاری)', 'body': 'متن نظر',
            'pros': 'نقاط قوت (اختیاری)', 'cons': 'نقاط ضعف (اختیاری)',
        }
        widgets = {
            'title': forms.TextInput(attrs={'maxlength': 100, 'placeholder': 'مثلاً: گوشی عالی با دوربین فوق‌العاده'}),
            'body': forms.Textarea(attrs={'rows': 4, 'maxlength': 1500, 'placeholder': 'تجربه خودتان از استفاده از این محصول را بنویسید...'}),
            'pros': forms.Textarea(attrs={'rows': 3, 'placeholder': 'هر مورد در یک خط'}),
            'cons': forms.Textarea(attrs={'rows': 3, 'placeholder': 'هر مورد در یک خط'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body'].required = True
        # The saved boolean must map back to the radio values
        if self.instance.pk and self.instance.recommend is not None:
            self.initial['recommend'] = '1' if self.instance.recommend else '0'

    def clean_recommend(self):
        value = self.cleaned_data.get('recommend')
        return None if value in (None, '') else value == '1'

    def clean_title(self):
        title = ' '.join(self.cleaned_data.get('title', '').split())
        _reject_contact_info(title)
        return title

    def clean_body(self):
        body = re.sub(r'\n{3,}', '\n\n', self.cleaned_data['body'].strip())
        if len(body) < 15:
            raise ValidationError('متن نظر باید حداقل ۱۵ حرف باشد.')
        _reject_contact_info(body)
        return body

    def _clean_lines(self, name):
        lines = []
        for raw in self.cleaned_data.get(name, '').splitlines():
            line = ' '.join(raw.split())
            if line and line not in lines:
                lines.append(line)
        if len(lines) > 5:
            raise ValidationError('حداکثر ۵ مورد مجاز است.')
        for line in lines:
            if len(line) > 80:
                raise ValidationError('هر مورد حداکثر ۸۰ حرف باشد.')
            _reject_contact_info(line)
        return '\n'.join(lines)

    def clean_pros(self):
        return self._clean_lines('pros')

    def clean_cons(self):
        return self._clean_lines('cons')