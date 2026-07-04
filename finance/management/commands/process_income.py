import os
import django
from django.core.management.base import BaseCommand


def setup_django():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WealthWise.settings')
    django.setup()


def get_process_daily_income():
    from finance.views import process_daily_income
    return process_daily_income


class Command(BaseCommand):
    help = 'Crédite les revenus journaliers et met à jour les cycles pour les packs dus.'

    def handle(self, *args, **options):
        setup_django()
        process_daily_income = get_process_daily_income()
        result = process_daily_income()
        self.stdout.write(self.style.SUCCESS(result))


if __name__ == '__main__':
    setup_django()
    process_daily_income = get_process_daily_income()
    print(process_daily_income())