from django.test import SimpleTestCase

from accounts.services.account_catalog_labels import (
    license_product_line,
    order_product_line,
    plan_account_label,
    product_account_label,
)


class _ProductStub:
    def __init__(self, *, title='', short_description='', slug=''):
        self.title = title
        self.short_description = short_description
        self.slug = slug


class _PlanStub:
    def __init__(self, *, name='', tagline='', plan_type='yearly', duration_days=None, product=None):
        self.name = name
        self.tagline = tagline
        self.plan_type = plan_type
        self.duration_days = duration_days
        self.product = product

    def get_plan_type_display(self):
        return {'yearly': 'یک‌ساله', 'lifetime': 'مادام‌العمر'}.get(self.plan_type, self.plan_type)


class _OrderStub:
    def __init__(self, *, product=None, plan=None):
        self.product = product
        self.plan = plan


class _LicenseStub:
    def __init__(self, *, order=None):
        self.order = order


class AccountCatalogLabelsTests(SimpleTestCase):
    def test_english_seed_product_to_persian(self):
        product = _ProductStub(title='Local Agency Plan', slug='local-agency-plan')
        self.assertEqual(product_account_label(product), 'پلن آژانس (میزکار تیمی)')

    def test_persian_title_unchanged(self):
        product = _ProductStub(title='ربات استخراج دیوار')
        self.assertEqual(product_account_label(product), 'ربات استخراج دیوار')

    def test_plan_english_name_maps(self):
        plan = _PlanStub(name='Local Agency', plan_type='yearly')
        self.assertEqual(plan_account_label(plan), 'آژانس محلی')

    def test_order_and_license_lines(self):
        product = _ProductStub(title='Agency Test')
        plan = _PlanStub(name='Agency Test Plan', product=product)
        order = _OrderStub(product=product, plan=plan)
        lic = _LicenseStub(order=order)
        self.assertEqual(order_product_line(order), 'آژانس — محیط تست')
        self.assertIn('آژانس', license_product_line(lic))
