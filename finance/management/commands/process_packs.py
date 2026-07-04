"""
Management command to process expired packs and withdrawal suspensions.
Run this as a cron job: python manage.py process_packs
"""
from django.core.management.base import BaseCommand
from finance.views import process_expired_packs, process_withdrawal_suspensions


class Command(BaseCommand):
    help = 'Process expired packs and withdrawal suspensions'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Processing expired packs...'))
        result_packs = process_expired_packs()
        self.stdout.write(self.style.SUCCESS(result_packs))
        
        self.stdout.write(self.style.SUCCESS('Processing withdrawal suspensions...'))
        result_suspensions = process_withdrawal_suspensions()
        self.stdout.write(self.style.SUCCESS(result_suspensions))
