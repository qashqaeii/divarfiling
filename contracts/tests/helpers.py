"""ابزارهای مشترک تست قرارداد."""
from licenses.models import License
from shop.models import LicensePlan, Order, Product


def grant_bot_license(user):
    """ایجاد لایسنس فعال برای تست‌های قرارداد."""
    product = Product.objects.filter(slug='test-bot-contracts').first()
    if not product:
        product = Product.objects.create(
            title='ربات تست قرارداد',
            slug='test-bot-contracts',
            description='محصول تست',
            is_active=True,
        )
    plan = LicensePlan.objects.filter(product=product, name='تست قرارداد').first()
    if not plan:
        plan = LicensePlan.objects.create(
            product=product,
            name='تست قرارداد',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
    order = Order.objects.create(
        user=user,
        product=product,
        plan=plan,
        amount=plan.price,
        status='paid',
    )
    return License.objects.create(
        order=order,
        plan=plan,
        license_key=f'TEST-CT-{user.pk}',
        status='active',
        max_activations=1,
    )
