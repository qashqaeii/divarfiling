# بازیابی تکمیل سفارش (پرداخت vs تمدید)

## مشکل

پس از **verify** زیبال، مبلغ از مشتری گرفته شده است. وضعیت `paid` باید **هرگز** به‌خاطر خطای تمدید Rollback نشود.

## معماری

1. `mark_order_paid_after_gateway` — تراکنش کوتاه، همیشه `paid`
2. `complete_order_fulfillment` — صدور/تمدید؛ در خطا `fulfillment_status` ∈ `pending|partial|failed`
3. `reconcile_order_fulfillments` — کرون + استعلام مجدد verify برای ناهمگامی درگاه

## فیلدها روی `Order`

| فیلد | معنی |
|------|------|
| `fulfillment_status` | complete / pending / partial / failed |
| `fulfillment_error` | آخرین خطا |
| `fulfillment_checked_at` | زمان آخرین ارزیابی |

## کرون پیشنهادی (Production)

```bash
# هر ۱۰ دقیقه — تمدید ناقص + ناهمگامی درگاه
python manage.py reconcile_order_fulfillments --limit 100

# یک سفارش خاص
python manage.py reconcile_order_fulfillments --order-id <uuid>
```

## Windows Task Scheduler / cron

هم‌مسیر با سایر jobهای Django در `django/docs/deploy.md` ثبت شود.
