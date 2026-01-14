from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.main.models import Parcel
from apps.main.auto_status import (
    _advance_cn_flow,
    _advance_local_flow,
    _get_received_after,
    _get_local_bishkek_after,
    _get_local_classify_after,
)


class Command(BaseCommand):
    help = "Advance parcels flows by time."

    def handle(self, *args, **options):
        processed = 0
        changed_total = 0

        while True:
            now = timezone.now().replace(microsecond=0)

            received_after = _get_received_after()
            bishkek_after = _get_local_bishkek_after()
            classify_after = bishkek_after + _get_local_classify_after()

            # границы "дозрел/не дозрел"
            t10 = now - timedelta(seconds=10)
            t2d = now - timedelta(days=2)
            t4d = now - timedelta(days=4)
            t_received = now - received_after

            t_bishkek = now - bishkek_after
            t_classify = now - classify_after

            due_cn = (
                Q(auto_flow_started_at__isnull=False)
                & (
                    Q(auto_flow_stage__lt=1)
                    | (Q(auto_flow_stage__lt=2) & Q(auto_flow_started_at__lte=t10))
                    | (Q(auto_flow_stage__lt=3) & Q(auto_flow_started_at__lte=t2d))
                    | (Q(auto_flow_stage__lt=4) & Q(auto_flow_started_at__lte=t4d))
                    | (Q(auto_flow_started_at__lte=t_received) & ~Q(status=Parcel.Status.RECEIVED))
                )
            )

            due_local = (
                Q(local_flow_started_at__isnull=False)
                & ~Q(status=Parcel.Status.RECEIVED)
                & (
                    (Q(local_flow_stage__lt=1) & Q(local_flow_started_at__lte=t_bishkek))
                    | (Q(local_flow_stage__lt=2) & Q(local_flow_started_at__lte=t_classify))
                )
            )

            with transaction.atomic():
                batch = list(
                    Parcel.objects
                    .exclude(status=Parcel.Status.RECEIVED)
                    .filter(due_cn | due_local)
                    .order_by("id")
                    .select_for_update(skip_locked=True)[:200]
                )

                if not batch:
                    break

                for p in batch:
                    before_status = p.status
                    before_af = p.auto_flow_stage
                    before_lf = p.local_flow_stage

                    _advance_cn_flow(p, now)
                    _advance_local_flow(p, None, now)

                    processed += 1

                    if (
                        p.status != before_status
                        or p.auto_flow_stage != before_af
                        or p.local_flow_stage != before_lf
                    ):
                        changed_total += 1

        self.stdout.write(self.style.SUCCESS(
            f"Processed: {processed}, Changed: {changed_total}"
        ))
