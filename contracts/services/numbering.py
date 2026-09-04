"""تولید شناسه داخلی قرارداد."""
from __future__ import annotations

import jdatetime

from django.db import transaction
from django.db.models import Max

from contracts.constants import CONTRACT_TYPE_PREFIX
from contracts.models import Contract


def generate_internal_number(contract_type: str) -> str:
    prefix = CONTRACT_TYPE_PREFIX.get(contract_type, 'GEN')
    now = jdatetime.datetime.now()
    year = now.year
    key_prefix = f'DF-{prefix}-{year}-'

    with transaction.atomic():
        last = (
            Contract.objects.select_for_update()
            .filter(internal_number__startswith=key_prefix)
            .aggregate(m=Max('internal_number'))['m']
        )
        if last:
            try:
                seq = int(last.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f'{key_prefix}{seq:06d}'
