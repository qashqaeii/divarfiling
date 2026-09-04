"""محافظت از نسخه‌های immutable."""
from __future__ import annotations

from contracts.models import ContractVersion


class VersionImmutableError(Exception):
    pass


def assert_version_mutable(version: ContractVersion) -> None:
    if version.is_locked:
        raise VersionImmutableError('این نسخه قابل ویرایش نیست.')


def assert_version_not_finalized(version: ContractVersion) -> None:
    contract = version.contract
    if contract.status == 'finalized' and version.is_published:
        raise VersionImmutableError('نسخه نهایی‌شده قابل تغییر نیست.')
