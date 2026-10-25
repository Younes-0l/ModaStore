from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify


# Create your models here.

class SlugModel(models.Model):
    """Abstract base: a name plus an auto-generated unique unicode slug."""

    name = models.CharField('نام', max_length=200)
    slug = models.SlugField('اسلاگ', max_length=220, unique=True, allow_unicode=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base = (slugify(self.name, allow_unicode=True) or 'item')[:200]
        slug, counter = base, 2
        manager = type(self)._default_manager
        while manager.filter(slug=slug).exists():
            slug = f'{base}-{counter}'
            counter += 1
        return slug


class Category(SlugModel):
    parent = models.ForeignKey(
        'self', verbose_name='دسته والد', null=True, blank=True,
        on_delete=models.PROTECT, related_name='children',
    )
    image = models.ImageField('تصویر', upload_to='categories/', blank=True)
    is_active = models.BooleanField('فعال', default=True)
    order = models.PositiveIntegerField('ترتیب نمایش', default=0)

    class Meta:
        verbose_name = 'دسته‌بندی'
        verbose_name_plural = 'دسته‌بندی‌ها'
        ordering = ['order', 'name']

    def clean(self):
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError('یک دسته نمی‌تواند والد خودش باشد.')


class Brand(SlugModel):
    logo = models.ImageField('لوگو', upload_to='brands/', blank=True)
    is_active = models.BooleanField('فعال', default=True)

    class Meta:
        verbose_name = 'برند'
        verbose_name_plural = 'برندها'
        ordering = ['name']


class Attribute(SlugModel):
    """A spec definition, e.g. 'RAM' or 'Screen size'."""

    group = models.CharField('گروه مشخصات', max_length=100, blank=True, help_text='مثلاً: صفحه‌نمایش، دوربین، باتری')
    categories = models.ManyToManyField(Category, verbose_name='دسته‌بندی‌های مرتبط', related_name='attributes', blank=True)
    is_filterable = models.BooleanField('قابل فیلتر', default=False)
    order = models.PositiveIntegerField('ترتیب نمایش', default=0)

    class Meta:
        verbose_name = 'ویژگی'
        verbose_name_plural = 'ویژگی‌ها'
        ordering = ['group', 'order', 'name']


class AttributeValue(models.Model):
    """A possible value of an attribute, e.g. RAM -> '8 GB'."""

    attribute = models.ForeignKey(Attribute, verbose_name='ویژگی', on_delete=models.CASCADE, related_name='values')
    value = models.CharField('مقدار', max_length=150)

    class Meta:
        verbose_name = 'مقدار ویژگی'
        verbose_name_plural = 'مقادیر ویژگی‌ها'
        ordering = ['attribute', 'value']
        constraints = [
            models.UniqueConstraint(
                fields=['attribute', 'value'], name='unique_attribute_value',
            ),
        ]

    def __str__(self):
        return f'{self.attribute.name}: {self.value}'


class Product(SlugModel):
    # Relations
    brand = models.ForeignKey(Brand, verbose_name='برند', on_delete=models.PROTECT, related_name='products')
    category = models.ForeignKey(Category, verbose_name='دسته‌بندی', on_delete=models.PROTECT, related_name='products')
    attribute_values = models.ManyToManyField(AttributeValue, through='ProductAttribute', related_name='products', blank=True)
    # Data Fields
    description = models.TextField('توضیحات', blank=True)
    is_active = models.BooleanField('فعال', default=True)
    # Date Fields
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین بروزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_active', '-created_at'])]


class ProductAttribute(models.Model):
    """Through model linking a product to its spec values."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_links')
    value = models.ForeignKey(AttributeValue, verbose_name='مقدار ویژگی', on_delete=models.PROTECT, related_name='product_links')

    class Meta:
        verbose_name = 'مشخصه محصول'
        verbose_name_plural = 'مشخصات محصول'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'value'], name='unique_product_value',
            ),
        ]

    def __str__(self):
        return f'{self.product} - {self.value}'


class ProductVariant(models.Model):
    """A purchasable unit: one color/storage combination with its own price and stock."""

    # Relations
    product = models.ForeignKey(Product, verbose_name='محصول', on_delete=models.CASCADE, related_name='variants')
    # Data Fields
    sku = models.CharField('کد SKU', max_length=50, unique=True)
    color = models.CharField('رنگ', max_length=50, blank=True)
    color_hex = models.CharField('کد رنگ', max_length=7, blank=True, help_text='مثلاً #1F2937')
    storage = models.CharField('حافظه', max_length=50, blank=True, help_text='مثلاً 256GB')
    is_active = models.BooleanField('فعال', default=True)
    # Integer Fields
    price = models.PositiveBigIntegerField('قیمت (تومان)')
    old_price = models.PositiveBigIntegerField('قیمت قبل از تخفیف (تومان)', null=True, blank=True)
    stock = models.PositiveIntegerField('موجودی', default=0)

    class Meta:
        verbose_name = 'تنوع محصول'
        verbose_name_plural = 'تنوع‌های محصول'
        ordering = ['price']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color', 'storage'],
                name='unique_variant_combination',
            ),
        ]

    def __str__(self):
        parts = [self.product.name, self.color, self.storage]
        return ' - '.join(p for p in parts if p)

    def clean(self):
        if self.old_price is not None and self.old_price <= self.price:
            raise ValidationError({'old_price': 'قیمت قبل از تخفیف باید بیشتر از قیمت فعلی باشد.'})

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return round((self.old_price - self.price) * 100 / self.old_price)
        return 0


class ProductImage(models.Model):
    # Relations
    product = models.ForeignKey(Product, verbose_name='محصول', on_delete=models.CASCADE, related_name='images')
    # File Fields
    image = models.ImageField('تصویر', upload_to='products/')
    # Data Fields
    alt = models.CharField('متن جایگزین', max_length=200, blank=True)
    is_main = models.BooleanField('تصویر اصلی', default=False)
    order = models.PositiveIntegerField('ترتیب', default=0)

    class Meta:
        verbose_name = 'تصویر محصول'
        verbose_name_plural = 'تصاویر محصول'
        ordering = ['-is_main', 'order']
        constraints = [
            # At most one main image per product
            models.UniqueConstraint(
                fields=['product'], condition=models.Q(is_main=True),
                name='unique_main_image_per_product',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} ({self.pk})'