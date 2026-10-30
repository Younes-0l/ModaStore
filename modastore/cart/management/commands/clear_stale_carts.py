from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from cart.models import Cart


class Command(BaseCommand):
    help = 'Delete guest carts that have not been touched for N days.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['days'])
        deleted, _ = Cart.objects.filter(user__isnull=True, updated_at__lt=cutoff).delete()
        self.stdout.write(f'Deleted {deleted} rows.')