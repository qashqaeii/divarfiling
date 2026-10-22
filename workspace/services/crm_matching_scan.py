"""جمع‌آوری کاندیدا برای امتیازدهی — کاهش bias صرفاً زمانی."""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from django.db.models import F, QuerySet, Value
from django.db.models.functions import Abs


def collect_match_scan_pool(
    qs: QuerySet,
    scan_limit: int,
    *,
    recency_field: str = 'updated_at',
    budget_field: Optional[str] = None,
    budget_target: Optional[int] = None,
) -> List:
    """ترکیب تازه‌ترین‌ها و نزدیک‌ترین‌ها به بودجه هدف در یک سبد اسکن."""
    if scan_limit <= 0:
        return []
    total = qs.count()
    if total <= scan_limit:
        return list(qs.order_by(f'-{recency_field}')[:scan_limit])

    half = max(scan_limit // 2, scan_limit - 400)
    recent = list(
        qs.order_by(f'-{recency_field}').values_list('pk', flat=True)[:half]
    )
    remaining = scan_limit - len(recent)
    rest_qs = qs.exclude(pk__in=recent)

    if budget_field and budget_target and remaining > 0:
        rest_ids = list(
            rest_qs.annotate(
                _budget_gap=Abs(F(budget_field) - Value(int(budget_target))),
            )
            .order_by('_budget_gap', f'-{recency_field}')
            .values_list('pk', flat=True)[:remaining]
        )
    else:
        rest_ids = list(
            rest_qs.order_by(f'-{recency_field}')
            .values_list('pk', flat=True)[:remaining]
        )

    id_order: Sequence[int] = list(dict.fromkeys(recent + rest_ids))
    if not id_order:
        return []
    by_pk = {obj.pk: obj for obj in qs.filter(pk__in=id_order)}
    return [by_pk[pk] for pk in id_order if pk in by_pk]
