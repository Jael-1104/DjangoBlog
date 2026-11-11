from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '检查 BlogUser 中重复/为空的邮箱，迁移前请先清洗'

    def handle(self, *args, **options):
        User = get_user_model()
        rows = list(User.objects.values_list('id', 'email'))
        counter = Counter(email for _, email in rows if email)
        duplicates = {e: c for e, c in counter.items() if c > 1}
        blanks = [uid for uid, email in rows if not email]

        for email, count in sorted(duplicates.items()):
            ids = [uid for uid, e in rows if e == email]
            self.stdout.write(self.style.ERROR(f'重复邮箱 {email} x{count}: ids={ids}'))
        if blanks:
            self.stdout.write(self.style.WARNING(f'空邮箱用户: ids={blanks}'))

        if not duplicates and not blanks:
            self.stdout.write(self.style.SUCCESS('邮箱数据干净，可以执行迁移'))
