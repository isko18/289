from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.main.models import Parcel
from apps.main.auto_status import _advance_cn_flow


class Command(BaseCommand):
    help = "Advance parcels flows by time (Postgres, CN only, 3 steps)."

    def handle(self, *args, **options):
        processed = 0
        changed_total = 0

        while True:
            now = timezone.now().replace(microsecond=0)

            # ЛОГИКА КАК НА СКРИНЕ:
            # stage 1: сразу (t0)
            # stage 2: +10 секунд
            # stage 3: +2 дня
            t10 = now - timedelta(seconds=10)
            t2d = now - timedelta(days=2)

            due_cn = (
                Q(auto_flow_started_at__isnull=False)
                & (
                    Q(auto_flow_stage__lt=1)
                    | (Q(auto_flow_stage__lt=2) & Q(auto_flow_started_at__lte=t10))
                    | (Q(auto_flow_stage__lt=3) & Q(auto_flow_started_at__lte=t2d))
                )
            )

            with transaction.atomic():
                batch = list(
                    Parcel.objects
                    .filter(due_cn)
                    .order_by("id")
                    .select_for_update(skip_locked=True)[:200]
                )

                if not batch:
                    break

                for p in batch:
                    before_status = p.status
                    before_stage = p.auto_flow_stage

                    _advance_cn_flow(p, now)

                    processed += 1
                    if p.status != before_status or p.auto_flow_stage != before_stage:
                        changed_total += 1

        self.stdout.write(self.style.SUCCESS(
            f"Processed: {processed}, Changed: {changed_total}"
        ))
