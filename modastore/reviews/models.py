from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator


# Create your models here.

class Review(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار تأیید'
        APPROVED = 'approved', 'تأیید شده'
        REJECTED = 'rejected', 'رد شده'

    product = models.ForeignKey(
        'catalog.Product', verbose_name='محصول',
        on_delete=models.CASCADE, related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='کاربر',
        on_delete=models.CASCADE, related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(
        'امتیاز', validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField('عنوان', max_length=100, blank=True)
    body = models.TextField('متن نظر', max_length=1500)
    pros = models.TextField('نقاط قوت', blank=True, help_text='هر مورد در یک خط')
    cons = models.TextField('نقاط ضعف', blank=True, help_text='هر مورد در یک خط')
    recommend = models.BooleanField('پیشنهاد می‌کنم', null=True, blank=True)

    status = models.CharField(
        'وضعیت', max_length=10, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    # Snapshot taken at submit time from the user's paid orders
    is_verified_buyer = models.BooleanField('خریدار', default=False)
    purchased_variant = models.CharField('تنوع خریداری‌شده', max_length=120, blank=True)
    helpful_count = models.PositiveIntegerField('تعداد رأی مفید', default=0)

    store_reply = models.TextField('پاسخ فروشگاه', blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    moderated_at = models.DateTimeField('تاریخ بررسی', null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', verbose_name='بررسی‌کننده',
    )

    class Meta:
        verbose_name = 'نظر'
        verbose_name_plural = 'نظرات'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='one_review_per_user_product'),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_1_to_5',
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'status', '-created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.product} - {self.rating}★'

    @property
    def pros_list(self):
        return [ln for ln in self.pros.splitlines() if ln.strip()]

    @property
    def cons_list(self):
        return [ln for ln in self.cons.splitlines() if ln.strip()]

    @property
    def display_name(self):
        """Masked name: the phone number is never shown publicly."""
        first = self.user.first_name.strip()
        if not first:
            return 'کاربر ModaStore'
        last = self.user.last_name.strip()
        return f'{first} {last[0]}.' if last else first

    @property
    def avatar_letter(self):
        return (self.user.first_name.strip() or 'م')[0]

    @property
    def avatar_class(self):
        return f'av-{self.user_id % 6}'


class ReviewVote(models.Model):
    """A user's "this review was helpful" vote."""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_votes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رأی مفید'
        verbose_name_plural = 'رأی‌های مفید'
        constraints = [
            models.UniqueConstraint(fields=['review', 'user'], name='one_vote_per_user_review'),
        ]