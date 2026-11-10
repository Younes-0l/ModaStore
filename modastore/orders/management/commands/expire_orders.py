from django.core.management.base import BaseCommand

from orders.services import services


class Command(BaseCommand):
    help = 'Cancel unpaid orders whose payment window is over and release their stock.'

    def handle(self, *args, **options):
        self.stdout.write(f'Canceled {services.expire_overdue_orders()} orders.')