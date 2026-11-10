from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from accounts.services.validators import normalize_digits, normalize_phone

PERSIAN = '۰۹۱۲۳۴۵۶۷۸۹'   # 09123456789
ARABIC = '٠٩١٢٣٤٥٦٧٨٩'    # 09123456789


class NormalizePhoneTests(SimpleTestCase):
    def test_accepted_formats_are_converted_to_canonical_form(self):
        samples = [
            '09123456789', '+989123456789', '00989123456789', '989123456789',
            '9123456789', PERSIAN, ARABIC, '0912 345 6789', '0912-345-6789',
        ]
        for raw in samples:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), '09123456789')

    def test_invalid_numbers_are_rejected(self):
        samples = ['', None, '12345', '08123456789', '0912345678', '091234567890',
                   'abcdefghijk', '+1555123456']
        for raw in samples:
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_phone(raw)


class NormalizeDigitsTests(SimpleTestCase):
    def test_persian_and_arabic_digits_become_ascii(self):
        self.assertEqual(normalize_digits('۱۲۳۴۵۶'), '123456')
        self.assertEqual(normalize_digits(' ١٢٣ '), '123')

    def test_none_is_safe(self):
        self.assertEqual(normalize_digits(None), '')
