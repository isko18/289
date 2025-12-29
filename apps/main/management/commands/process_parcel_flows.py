from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.main.models import Parcel
from apps.main.auto_status import _advance_cn_flow, _advance_local_flow


class Command(BaseCommand):
    help = "Advance parcels flows by time."

    def handle(self, *args, **options):
        now = timezone.now().replace(microsecond=0)

        qs = (
            Parcel.objects
            .filter(auto_flow_started_at__isnull=False)
            .exclude(status=Parcel.Status.RECEIVED)
            .order_by("id")
        )

        processed = 0
        while True:
            with transaction.atomic():
                batch = list(qs.select_for_update(skip_locked=True)[:200])
                if not batch:
                    break
                for p in batch:
                    _advance_cn_flow(p, now)
                    _advance_local_flow(p, None, now)
                    processed += 1

        self.stdout.write(self.style.SUCCESS(f"Processed: {processed}"))
