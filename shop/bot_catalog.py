"""کاتالوگ محتوای محصول واحد — ربات استخراج دیوار."""
from django.urls import reverse

from divar_shop.brand import site_brand_context

BOT_PRODUCT_SLUG = 'divar-extraction-bot'


def footer_content():
    """محتوای فوتر سایت عمومی."""
    brand = site_brand_context()
    return {
        'tagline': 'پلتفرم استخراج، فایلینگ، CRM و تحلیل بازار املاک — یک میزکار یکپارچه برای مشاوران حرفه‌ای.',
        'trust_note': 'خرید امن با نماد اعتماد الکترونیکی',
        'legal': 'تمامی حقوق مادی و معنوی این وب‌سایت محفوظ است.',
        'creator_line': f'توسعه: {brand["creator_name"]} · {brand["site_url_display"]}',
        'social': [
            {
                'icon': 'fab fa-telegram',
                'label': 'تلگرام سازنده',
                'href': brand['creator_telegram_url'],
            },
            {
                'icon': 'fas fa-phone-alt',
                'label': 'تماس',
                'href': f'tel:{brand["creator_phone_tel"]}',
            },
            {
                'icon': 'fas fa-envelope',
                'label': 'ایمیل',
                'href': f'mailto:{brand["support_email"]}',
            },
        ],
    }


def get_bot_product():
    from shop.models import Product

    return Product.objects.filter(slug=BOT_PRODUCT_SLUG, is_active=True).first()


def get_bot_product_url() -> str:
    product = get_bot_product()
    if product:
        return reverse('product_detail', kwargs={'slug': product.slug})
    return reverse('product_list')


def get_bot_product_buy_url(plan_id=None) -> str:
    product = get_bot_product()
    if not product:
        return reverse('product_list')
    url = reverse('buy', kwargs={'slug': product.slug})
    if plan_id:
        return f'{url}?plan={plan_id}'
    return url


def bot_product_defaults():
    """داده‌های پیش‌فرض برای sync محصول در دیتابیس."""
    return {
        'title': 'ربات استخراج دیوار',
        'short_description': (
            'استخراج خودکار آگهی‌های دیوار — ربات ویندوز برای حجم بالا، '
            'اپ اندروید برای CRM و کار میدانی؛ هر دو با یک لایسنس به میزکار متصل می‌شوند'
        ),
        'description': (
            '<p>ربات استخراج دیوار و اپ فایلینگ اندروید، ابزار اختصاصی مشاوران املاک '
            'برای جمع‌آوری آگهی‌ها از دیوار و مدیریت فایلینگ است. '
            'با یک لایسنس همزمان از ویندوز (استخراج حجیم) و اندروید (CRM، اعلان، استخراج سبک) '
            'استفاده کنید. داده‌ها در میزکار همگام می‌شوند — تحلیل، نقشه و CRM در اختیار شماست.</p>'
        ),
        'features': [
            'ربات ویندوز — استخراج موازی با سرعت بالا',
            'اپ اندروید — CRM، فایلینگ سبک و اعلان تطبیق ملک',
            'یک لایسنس — یک اسلات ویندوز + یک اسلات اندروید',
            'فیلتر استان، شهر، محله و نوع معامله',
            'ساخت خودکار پوشه output با ساختار فایلینگ (ویندوز)',
            'خروجی Excel، CSV و JSON',
            'همگام‌سازی فایلینگ با میزکار وب',
            'تحلیل آماری، نقشه و مقایسه فایل‌ها',
        ],
        'is_active': True,
        'order': 0,
    }


def _shared_license_features():
    """ویژگی‌های مشترک اکوسیستم — برای ترکیب با پلن‌ها."""
    return [
        {'text': 'ربات ویندوز — استخراج حجیم دیوار', 'icon': 'fa-robot'},
        {'text': 'اپ اندروید — CRM و فایلینگ موبایل', 'icon': 'fa-mobile-screen'},
        {'text': 'فایلینگ دیوار + تحلیل بازار', 'icon': 'fa-chart-line'},
        {'text': 'نقشه آگهی‌ها و مقایسه فایل‌ها', 'icon': 'fa-map-location-dot'},
        {'text': 'آپلود و همگام‌سازی در میزکار', 'icon': 'fa-cloud-upload-alt'},
    ]


def _shared_agency_features():
    """ویژگی‌های مشترک هر سه مدت پلن آژانس."""
    return [
        {'text': 'هر مشاور یک کلید مستقل', 'icon': 'fa-key'},
        {'text': 'هر کلید: ۱ ویندوز + ۱ اندروید', 'icon': 'fa-link'},
        {'text': 'CRM و مدیریت تیم', 'icon': 'fa-users-gear'},
        {'text': 'استخراج، فایلینگ و تحلیل', 'icon': 'fa-database'},
        {'text': 'تخصیص کلید به اعضای تیم', 'icon': 'fa-user-plus'},
        {'text': 'تخفیف بیشتر با افزایش تعداد', 'icon': 'fa-percent'},
        {'text': 'پشتیبانی راه‌اندازی آژانس', 'icon': 'fa-headset'},
    ]


def bot_plan_marketing_by_key():
    """
    tagline و features هر پلن — کلید: (plan_type, allow_bulk, order).
    با sync و seed_plan_features همگام نگه دارید.
    """
    return {
        ('daily', False, 0): {
            'tagline': 'آشنایی با محصول — قبل از تصمیم نهایی',
            'features': [
                {'text': '۷ روز دسترسی کامل به لایسنس', 'icon': 'fa-clock'},
                {'text': '۱ اسلات ویندوز + ۱ اسلات اندروید', 'icon': 'fa-link'},
                {'text': 'تست استخراج، فایلینگ و تحلیل', 'icon': 'fa-flask'},
                {'text': 'فعال‌سازی فوری پس از پرداخت', 'icon': 'fa-bolt'},
                {'text': 'پشتیبانی نصب و راه‌اندازی', 'icon': 'fa-headset'},
                {'text': 'محدود به یک‌بار برای هر حساب', 'icon': 'fa-user-check'},
            ],
        },
        ('monthly', False, 1): {
            'tagline': 'شروع حرفه‌ای — مناسب مشاور مستقل',
            'features': [
                {'text': '۳۰ روز دسترسی کامل', 'icon': 'fa-calendar-day'},
                {'text': '۱ ویندوز + ۱ اندروید', 'icon': 'fa-link'},
                *_shared_license_features()[0:3],
                {'text': 'فعال‌سازی فوری و پشتیبانی نصب', 'icon': 'fa-bolt'},
            ],
        },
        ('quarterly', False, 2): {
            'tagline': 'تعادل عالی قیمت و مدت — پرطرفدار',
            'features': [
                {'text': '۹۰ روز دسترسی بدون محدودیت', 'icon': 'fa-calendar-week'},
                {'text': '۱ ویندوز + ۱ اندروید', 'icon': 'fa-link'},
                *_shared_license_features(),
                {'text': 'پشتیبانی فنی در مدت لایسنس', 'icon': 'fa-headset'},
            ],
        },
        ('yearly', False, 3): {
            'tagline': 'بهترین ارزش — یک سال بدون دغدغه تمدید',
            'features': [
                {'text': '۳۶۵ روز دسترسی کامل', 'icon': 'fa-calendar'},
                {'text': '۱ ویندوز + ۱ اندروید', 'icon': 'fa-link'},
                *_shared_license_features(),
                {'text': 'به‌روزرسانی رایگان در مدت لایسنس', 'icon': 'fa-rotate'},
                {'text': 'اولویت در پشتیبانی', 'icon': 'fa-star'},
            ],
        },
        ('monthly', True, 4): {
            'tagline': 'مناسب تیم‌های ۲ تا ۲۵ مشاور',
            'features': [
                {'text': '۳۰ روز دسترسی هر لایسنس', 'icon': 'fa-calendar-day'},
                *_shared_agency_features(),
            ],
        },
        ('quarterly', True, 5): {
            'tagline': 'مناسب تیم‌های ۲ تا ۲۵ مشاور',
            'features': [
                {'text': '۹۰ روز دسترسی هر لایسنس', 'icon': 'fa-calendar-week'},
                *_shared_agency_features(),
            ],
        },
        ('yearly', True, 6): {
            'tagline': 'مناسب تیم‌های ۲ تا ۲۵ مشاور',
            'features': [
                {'text': '۳۶۵ روز دسترسی هر لایسنس', 'icon': 'fa-calendar'},
                *_shared_agency_features(),
            ],
        },
    }


def bot_plan_marketing_for_plan(plan_type: str, allow_bulk: bool, order: int) -> dict:
    catalog = bot_plan_marketing_by_key()
    return catalog.get((plan_type, allow_bulk, order), {'tagline': '', 'features': []})


def bot_license_plans():
    """پلن‌های پیش‌فرض لایسنس — آزمایشی، فردی و آژانس."""
    base_plans = [
        {
            'name': 'پلن آزمایشی ۱ هفته‌ای',
            'plan_type': 'daily',
            'price': 250_000,
            'duration_days': 7,
            'max_activations': 2,
            'order': 0,
        },
        {
            'name': 'لایسنس یک‌ماهه',
            'plan_type': 'monthly',
            'price': 990_000,
            'duration_days': 30,
            'max_activations': 2,
            'order': 1,
        },
        {
            'name': 'لایسنس سه‌ماهه',
            'plan_type': 'quarterly',
            'price': 2_500_000,
            'duration_days': 90,
            'max_activations': 2,
            'order': 2,
        },
        {
            'name': 'لایسنس یک‌ساله',
            'plan_type': 'yearly',
            'price': 8_000_000,
            'compare_at_price': 10_000_000,
            'duration_days': 365,
            'max_activations': 2,
            'offer_badge': 'آفر ویژه',
            'order': 3,
        },
        {
            'name': 'پلن آژانس — ماهانه',
            'plan_type': 'monthly',
            'price': 990_000,
            'duration_days': 30,
            'max_activations': 2,
            'allow_bulk_purchase': True,
            'min_quantity': 2,
            'max_quantity': 25,
            'offer_badge': 'آژانس',
            'order': 4,
        },
        {
            'name': 'پلن آژانس — سه‌ماهه',
            'plan_type': 'quarterly',
            'price': 2_500_000,
            'duration_days': 90,
            'max_activations': 2,
            'allow_bulk_purchase': True,
            'min_quantity': 2,
            'max_quantity': 25,
            'offer_badge': 'آژانس',
            'order': 5,
        },
        {
            'name': 'پلن آژانس — سالانه',
            'plan_type': 'yearly',
            'price': 8_000_000,
            'compare_at_price': 10_000_000,
            'duration_days': 365,
            'max_activations': 2,
            'allow_bulk_purchase': True,
            'min_quantity': 2,
            'max_quantity': 25,
            'offer_badge': 'آژانس',
            'order': 6,
        },
    ]
    for plan in base_plans:
        marketing = bot_plan_marketing_for_plan(
            plan['plan_type'],
            plan.get('allow_bulk_purchase', False),
            plan['order'],
        )
        plan['tagline'] = marketing.get('tagline', '')
        plan['features'] = marketing.get('features', [])
    return base_plans


def extraction_tree_content():
    """درخت ساختار استخراج — برای نمایش تعاملی در صفحه محصول."""
    shared = [
        {
            'id': 'identity',
            'label': 'شناسه و لینک',
            'icon': 'fa-fingerprint',
            'accent': 'violet',
            'fields': ['شناسه یکتا (token)', 'لینک آگهی', 'share_link'],
        },
        {
            'id': 'content',
            'label': 'عنوان و متن',
            'icon': 'fa-file-lines',
            'accent': 'sky',
            'fields': ['عنوان', 'زیرعنوان', 'توضیحات کامل'],
        },
        {
            'id': 'location',
            'label': 'موقعیت مکانی',
            'icon': 'fa-location-dot',
            'accent': 'emerald',
            'fields': ['شهر', 'محله', 'آدرس', 'عرض و طول جغرافیایی', 'شعاع محدوده نقشه'],
        },
        {
            'id': 'publisher',
            'label': 'آگهی‌دهنده',
            'icon': 'fa-user-tie',
            'accent': 'amber',
            'fields': ['نوع آگهی‌دهنده (مالک / مشاور)', 'وضعیت تماس', 'چت فعال'],
        },
        {
            'id': 'taxonomy',
            'label': 'دسته‌بندی و زمان',
            'icon': 'fa-tags',
            'accent': 'rose',
            'fields': ['دسته سطح ۱/۲/۳', 'برچسب‌ها', 'تاریخ انتشار', 'تاریخ انقضا'],
        },
        {
            'id': 'media',
            'label': 'رسانه',
            'icon': 'fa-images',
            'accent': 'cyan',
            'fields': ['تصاویر (URL)', 'تعداد تصویر', 'ویدیو', 'دانلود در پوشه output'],
        },
    ]

    categories = [
        {
            'id': 'sale-residential',
            'label': 'فروش مسکونی',
            'icon': 'fa-house',
            'accent': 'violet',
            'desc': 'آپارتمان، خانه و ویلا، کلنگی — با قیمت کل و قیمت هر متر',
            'output_prefix': 'فروش',
            'subcategories': [
                {'label': 'آپارتمان', 'file': 'فروش_آپارتمان.xlsx'},
                {'label': 'خانه و ویلا', 'file': 'فروش_خانه_ویلا.xlsx'},
                {'label': 'کلنگی', 'file': 'فروش_کلنگی.xlsx'},
            ],
            'price_layer': {
                'label': 'قیمت‌گذاری فروش',
                'icon': 'fa-coins',
                'fields': ['قیمت کل (عدد + نمایش)', 'قیمت هر متر', 'ارز', 'price_text'],
            },
            'spec_layers': [
                {
                    'label': 'مشخصات ملک',
                    'icon': 'fa-ruler-combined',
                    'fields': ['متراژ', 'تعداد اتاق', 'طبقه', 'سال ساخت', 'سن بنا'],
                },
                {
                    'label': 'امکانات',
                    'icon': 'fa-star',
                    'fields': ['آسانسور', 'پارکینگ', 'انباری', 'استخر', 'لابی', 'بالکن'],
                },
                {
                    'label': 'جزئیات تکمیلی',
                    'icon': 'fa-list-check',
                    'fields': ['جهت ساختمان', 'نوع آشپزخانه', 'سند', 'وضعیت سکونت', 'قابل معاوضه'],
                },
            ],
            'sample': {
                'title': 'آپارتمان ۱۲۵ متری ۲ خواب — مرزداران',
                'file': 'فروش_آپارتمان.xlsx',
                'path': 'تهران/تهران/مرزداران/',
                'highlights': [
                    {'label': 'قیمت کل', 'value': '۵۰,۰۰۰,۰۰۰,۰۰۰ تومان'},
                    {'label': 'قیمت هر متر', 'value': '۴۰۰,۰۰۰,۰۰۰'},
                    {'label': 'متراژ', 'value': '۱۲۵ متر'},
                    {'label': 'اتاق', 'value': '۲ خواب (۱ مستر)'},
                ],
            },
        },
        {
            'id': 'rent-residential',
            'label': 'اجاره مسکونی',
            'icon': 'fa-key',
            'accent': 'sky',
            'desc': 'رهن و اجاره آپارتمان و خانه — ودیعه، اجاره ماهانه و قابلیت تبدیل',
            'output_prefix': 'اجاره',
            'subcategories': [
                {'label': 'آپارتمان', 'file': 'اجاره_آپارتمان.xlsx'},
                {'label': 'خانه و ویلا', 'file': 'اجاره_خانه_ویلا.xlsx'},
            ],
            'price_layer': {
                'label': 'رهن و اجاره',
                'icon': 'fa-hand-holding-dollar',
                'fields': ['ودیعه / رهن (عدد + نمایش)', 'اجاره ماهانه', 'قابل تبدیل / غیرقابل تبدیل', 'اسلایدر ودیعه↔اجاره'],
            },
            'spec_layers': [
                {
                    'label': 'مشخصات ملک',
                    'icon': 'fa-ruler-combined',
                    'fields': ['متراژ', 'اتاق', 'طبقه', 'سال ساخت', 'مبله / غیرمبله'],
                },
                {
                    'label': 'شرایط اجاره',
                    'icon': 'fa-file-contract',
                    'fields': ['حداقل مدت قرارداد', 'حیوان خانگی مجاز', 'وضعیت سکونت', 'تعداد ساکنین'],
                },
                {
                    'label': 'امکانات',
                    'icon': 'fa-star',
                    'fields': ['آسانسور', 'پارکینگ', 'انباری', 'سرمایش', 'گرمایش', 'آب گرم'],
                },
            ],
            'sample': {
                'title': 'آپارتمان ۹۰ متری ۲ خواب',
                'file': 'اجاره_آپارتمان.xlsx',
                'path': 'تهران/تهران/ونک/',
                'highlights': [
                    {'label': 'ودیعه', 'value': '۸۰۰,۰۰۰,۰۰۰ تومان'},
                    {'label': 'اجاره', 'value': '۲۵,۰۰۰,۰۰۰ / ماه'},
                    {'label': 'تبدیل', 'value': 'قابل تبدیل'},
                    {'label': 'متراژ', 'value': '۹۰ متر'},
                ],
            },
        },
        {
            'id': 'sale-commercial',
            'label': 'فروش اداری و تجاری',
            'icon': 'fa-building',
            'accent': 'indigo',
            'desc': 'دفتر، مغازه و ملک صنعتی — قیمت کل و مشخصات کاربری',
            'output_prefix': 'فروش اداری تجاری',
            'subcategories': [
                {'label': 'دفتر کار، مطب', 'file': 'فروش_دفتر.xlsx'},
                {'label': 'مغازه و غرفه', 'file': 'فروش_مغازه.xlsx'},
                {'label': 'صنعتی، کشاورزی', 'file': 'فروش_صنعتی.xlsx'},
            ],
            'price_layer': {
                'label': 'قیمت‌گذاری',
                'icon': 'fa-coins',
                'fields': ['قیمت کل', 'قیمت هر متر', 'قیمت پیشنهادی'],
            },
            'spec_layers': [
                {
                    'label': 'مشخصات فضا',
                    'icon': 'fa-store',
                    'fields': ['متراژ', 'طبقه', 'نوع کاربری', 'سال ساخت', 'عرض ملک'],
                },
                {
                    'label': 'امکانات تجاری',
                    'icon': 'fa-plug',
                    'fields': ['برق سه‌فاز', 'آب', 'گاز', 'سرویس بهداشتی', 'پارکینگ'],
                },
            ],
            'sample': {
                'title': 'مغازه ۴۵ متری پرتردد',
                'file': 'فروش_مغازه.xlsx',
                'path': 'فارس/شیراز/زند/',
                'highlights': [
                    {'label': 'قیمت', 'value': '۱۲,۰۰۰,۰۰۰,۰۰۰ تومان'},
                    {'label': 'متراژ', 'value': '۴۵ متر'},
                    {'label': 'کاربری', 'value': 'تجاری'},
                    {'label': 'طبقه', 'value': 'همکف'},
                ],
            },
        },
        {
            'id': 'rent-commercial',
            'label': 'اجاره اداری و تجاری',
            'icon': 'fa-store',
            'accent': 'cyan',
            'desc': 'اجاره دفتر، مغازه و فضای صنعتی — ودیعه و اجاره ماهانه',
            'output_prefix': 'اجاره اداری تجاری',
            'subcategories': [
                {'label': 'دفتر کار، مطب', 'file': 'اجاره_دفتر.xlsx'},
                {'label': 'مغازه و غرفه', 'file': 'اجاره_مغازه.xlsx'},
                {'label': 'صنعتی، کشاورزی', 'file': 'اجاره_صنعتی.xlsx'},
            ],
            'price_layer': {
                'label': 'رهن و اجاره',
                'icon': 'fa-hand-holding-dollar',
                'fields': ['ودیعه', 'اجاره ماهانه', 'قابل تبدیل', 'حداقل مدت قرارداد'],
            },
            'spec_layers': [
                {
                    'label': 'مشخصات فضا',
                    'icon': 'fa-store',
                    'fields': ['متراژ', 'طبقه', 'نوع کاربری', 'موقعیت ملک'],
                },
                {
                    'label': 'امکانات',
                    'icon': 'fa-plug',
                    'fields': ['برق', 'آب', 'گاز', 'انبار', 'پارکینگ'],
                },
            ],
            'sample': {
                'title': 'دفتر ۱۲۰ متری اداری',
                'file': 'اجاره_دفتر.xlsx',
                'path': 'تهران/تهران/سعادت‌آباد/',
                'highlights': [
                    {'label': 'ودیعه', 'value': '۵۰۰,۰۰۰,۰۰۰ تومان'},
                    {'label': 'اجاره', 'value': '۱۸,۰۰۰,۰۰۰ / ماه'},
                    {'label': 'متراژ', 'value': '۱۲۰ متر'},
                    {'label': 'طبقه', 'value': '۴'},
                ],
            },
        },
        {
            'id': 'construction',
            'label': 'پروژه‌های ساخت‌وساز',
            'icon': 'fa-hammer',
            'accent': 'amber',
            'desc': 'پیش‌فروش و پروژه‌های نوساز — قیمت پایه، متراژ و وضعیت پیشرفت',
            'output_prefix': 'پروژه',
            'subcategories': [
                {'label': 'پروژه ساخت‌وساز', 'file': 'پروژه_ساخت.xlsx'},
            ],
            'price_layer': {
                'label': 'قیمت پروژه',
                'icon': 'fa-coins',
                'fields': ['قیمت پایه', 'قیمت هر متر', 'پیش‌پرداخت', 'شرایط پرداخت'],
            },
            'spec_layers': [
                {
                    'label': 'مشخصات پروژه',
                    'icon': 'fa-building-columns',
                    'fields': ['متراژ', 'تعداد واحد', 'طبقات', 'سال تحویل', 'پیشرفت ساخت'],
                },
                {
                    'label': 'امکانات پروژه',
                    'icon': 'fa-star',
                    'fields': ['آسانسور', 'پارکینگ', 'لابی', 'استخر', 'سالن ورزش'],
                },
            ],
            'sample': {
                'title': 'برج مسکونی ۱۴ طبقه',
                'file': 'پروژه_ساخت.xlsx',
                'path': 'فارس/شیراز/قصرالدشت/',
                'highlights': [
                    {'label': 'قیمت از', 'value': '۳,۸۰۰,۰۰۰,۰۰۰'},
                    {'label': 'متراژ', 'value': '۷۵–۱۴۰ متر'},
                    {'label': 'تحویل', 'value': '۱۴۰۴'},
                    {'label': 'واحد', 'value': '۴۸ واحد'},
                ],
            },
        },
        {
            'id': 'land',
            'label': 'زمین و باغ',
            'icon': 'fa-tree',
            'accent': 'emerald',
            'desc': 'زمین مسکونی، تجاری و باغ — متراژ، کاربری و موقعیت',
            'output_prefix': 'زمین',
            'subcategories': [
                {'label': 'زمین و کلنگی', 'file': 'فروش_زمین.xlsx'},
                {'label': 'باغ و ویلا', 'file': 'فروش_باغ.xlsx'},
            ],
            'price_layer': {
                'label': 'قیمت‌گذاری',
                'icon': 'fa-coins',
                'fields': ['قیمت کل', 'قیمت هر متر', 'قابل معاوضه'],
            },
            'spec_layers': [
                {
                    'label': 'مشخصات زمین',
                    'icon': 'fa-map',
                    'fields': ['متراژ', 'عرض ملک', 'کاربری', 'بر خیابان', 'گذر'],
                },
                {
                    'label': 'مجوز و سند',
                    'icon': 'fa-file-contract',
                    'fields': ['نوع سند', 'مجوز ساخت', 'وضعیت بافت', 'قابل تفکیک'],
                },
            ],
            'sample': {
                'title': 'زمین ۳۰۰ متری مسکونی',
                'file': 'فروش_زمین.xlsx',
                'path': 'فارس/مرودشت/شهرک غرب/',
                'highlights': [
                    {'label': 'قیمت', 'value': '۹,۰۰۰,۰۰۰,۰۰۰ تومان'},
                    {'label': 'متراژ', 'value': '۳۰۰ متر'},
                    {'label': 'کاربری', 'value': 'مسکونی'},
                    {'label': 'سند', 'value': 'تک‌برگ'},
                ],
            },
        },
    ]

    return {
        'eyebrow': 'معماری داده',
        'title': 'ساختار استخراج',
        'subtitle': (
            'هر دسته‌بندی دیوار، لایه‌های دادهٔ مخصوص خود را دارد — '
            'روی شاخه‌ها کلیک کنید و ببینید دقیقاً چه فیلدهایی استخراج می‌شود.'
        ),
        'shared_label': 'لایه‌های مشترک همه دسته‌ها',
        'shared_layers': shared,
        'categories': categories,
        'stats': [
            {'value': '80+', 'label': 'فیلد قابل استخراج'},
            {'value': '6', 'label': 'دسته اصلی'},
            {'value': '3', 'label': 'فرمت خروجی'},
        ],
    }


def bot_page_content():
    """محتوای غنی صفحه محصول — مستقل از دیتابیس."""
    return {
        'tagline': 'محصول اصلی فایلینگ دیوار',
        'hero_lead': (
            'یک لایسنس — دو پلتفرم: ربات ویندوز برای استخراج حجیم و فایلینگ حرفه‌ای، '
            'اپ اندروید برای استخراج سبک، CRM و اعلان در جیب شما. '
            'هر دو به میزکار متصل می‌شوند — تحلیل، نقشه و پیگیری مشتری در یک جا.'
        ),
        'license_badge': 'یک لایسنس · ویندوز + اندروید',
        'pricing_note': (
            'هر پلن شامل یک اسلات ربات ویندوز و یک اسلات اپ اندروید است. '
            'در موبایل با همان حساب وارد شوید؛ در ویندوز کلید لایسنس را فعال کنید.'
        ),
        'platforms': {
            'eyebrow': 'دو پلتفرم، یک لایسنس',
            'title': 'ویندوز برای حجم بالا — اندروید برای کار میدانی',
            'subtitle': (
                'مشاور حرفه‌ای هر دو را دارد: ربات روی PC برای استخراج شبانه و حجیم، '
                'اپ روی گوشی برای CRM، اعلان تطبیق ملک و استخراج سریع محله.'
            ),
            'items': [
                {
                    'id': 'windows',
                    'accent': 'sky',
                    'icon': 'fab fa-windows',
                    'title': 'ربات ویندوز',
                    'tagline': 'استخراج حجیم · فایلینگ output · Excel و CSV',
                    'image': 'images/help-bot-extract-tab.png',
                    'image_alt': 'ربات استخراج دیوار — تب استخراج با فیلتر شهر و محله',
                    'lightbox_caption': 'ربات ویندوز — استخراج حرفه‌ای',
                    'highlights': [
                        'استخراج موازی چند منطقه و نوع معامله',
                        'پوشه output با ساختار استان / شهر / محله',
                        'خروجی Excel، CSV، JSON + تصاویر آگهی',
                        'فعال‌سازی با کلید لایسنس از داشبورد',
                    ],
                    'best_for': 'دفتر کار، استخراج شبانه، آرشیو حجیم',
                },
                {
                    'id': 'android',
                    'accent': 'emerald',
                    'icon': 'fab fa-android',
                    'title': 'اپ اندروید',
                    'tagline': 'CRM موبایل · اعلان · استخراج سبک',
                    'image': 'images/android/android-02-home.png',
                    'image_alt': 'اپ فایلینگ دیوار — داشبورد روزانه و میانبر استخراج',
                    'lightbox_caption': 'اپ اندروید — داشبورد فایلینگ',
                    'highlights': [
                        'ورود با همان حساب میزکار — بدون کپی کلید',
                        'CRM، مشتری، معامله و فایل ملک روی موبایل',
                        'اعلان تطبیق ملک و یادآور تماس',
                        'استخراج محله‌ای و زمان‌بندی خودکار',
                    ],
                    'best_for': 'بازدید میدانی، پیگیری مشتری، کار روزانه',
                },
            ],
        },
        'value_props': [
            {
                'icon': 'fa-bolt',
                'title': 'جمع‌آوری در چند ثانیه',
                'desc': 'ویندوز حجم بالا، اندروید استخراج سریع — هر دو خودکار و بدون کار دستی.',
            },
            {
                'icon': 'fa-mobile-screen',
                'title': 'CRM و اعلان در جیب',
                'desc': 'اپ اندروید: مشتری، معامله، تطبیق ملک و یادآور — حتی در مسیر.',
            },
            {
                'icon': 'fa-folder',
                'title': 'فایلینگ منظم',
                'desc': 'ویندوز: پوشه output با تفکیک استان، شهر، محله. اندروید: فایلینگ ابری در میزکار.',
            },
            {
                'icon': 'fa-layer-group',
                'title': 'یک میزکار برای همه',
                'desc': 'آپلود output یا همگام‌سازی مستقیم — تحلیل، نقشه و CRM در یک حساب.',
            },
        ],
        'journey_steps': [
            {
                'title': 'خرید لایسنس',
                'desc': 'پلن را انتخاب کنید — یک اسلات ویندوز + یک اسلات اندروید فعال می‌شود.',
                'icon': 'fa-cart-shopping',
            },
            {
                'title': 'فعال‌سازی دو پلتفرم',
                'desc': 'اپ اندروید با حساب میزکار؛ ربات ویندوز با کلید لایسنس از داشبورد.',
                'icon': 'fa-key',
            },
            {
                'title': 'استخراج آگهی‌ها',
                'desc': 'فیلتر شهر، محله و نوع معامله — ربات حجیم، اپ سبک و همراه.',
                'icon': 'fa-robot',
            },
            {
                'title': 'تحلیل و CRM',
                'desc': 'آپلود output یا همگام‌سازی مستقیم — نقشه، نمودار و پیگیری مشتری.',
                'icon': 'fa-chart-line',
            },
        ],
        'workflow_steps': [
            {
                'title': 'خرید لایسنس',
                'desc': 'پلن را انتخاب کنید — یک اسلات ویندوز + یک اسلات اندروید فعال می‌شود.',
                'icon': 'fa-cart-shopping',
            },
            {
                'title': 'فعال‌سازی اندروید',
                'desc': 'APK را نصب کنید و با همان حساب میزکار وارد شوید — بدون کپی کلید.',
                'icon': 'fa-mobile-screen',
            },
            {
                'title': 'نصب ربات ویندوز',
                'desc': 'نصب‌کننده را از داشبورد دانلود کنید و کلید لایسنس را در اولین اجرا وارد کنید.',
                'icon': 'fa-download',
            },
            {
                'title': 'استخراج آگهی‌ها',
                'desc': 'فیلتر شهر، محله و نوع معامله — ربات حجیم، اپ سبک و همراه.',
                'icon': 'fa-robot',
            },
            {
                'title': 'همگام با میزکار',
                'desc': 'پوشه output را آپلود کنید یا از اپ مستقیم در میزکار ببینید.',
                'icon': 'fa-cloud-arrow-up',
            },
            {
                'title': 'تحلیل و CRM',
                'desc': 'نمودار قیمت، نقشه، مقایسه فایل‌ها و پیوند آگهی‌ها به مخاطبین.',
                'icon': 'fa-chart-line',
            },
        ],
        'folder_tree': [
            'output/',
            '├── فارس/',
            '│   └── شیراز/',
            '│       ├── فروش_آپارتمان.xlsx',
            '│       └── اجاره_آپارتمان.xlsx',
            '└── تهران/',
            '    └── تهران/',
            '        └── بریانک/',
            '            ├── فروش_آپارتمان.xlsx',
            '            └── اجاره_ویلا.xlsx',
        ],
        'folder_notes': [
            'هر فایل Excel مربوط به یک ترکیب شهر/محله و نوع معامله است.',
            'به‌روزرسانی مجدد ربات، فایل همان مسیر را به‌روز می‌کند.',
            'می‌توانید کل پوشه output را یک‌جا در میزکار import کنید.',
            'تصاویر آگهی‌ها در زیرپوشه‌های مرتبط ذخیره می‌شوند.',
        ],
        'extraction_features': [
            {
                'icon': 'fa-filter',
                'title': 'فیلتر پیشرفته',
                'desc': 'استان، شهر، محله، نوع معامله، دسته ملک و حذف آگهی‌های نامرتبط',
            },
            {
                'icon': 'fa-gauge-high',
                'title': 'استخراج موازی',
                'desc': 'چند منطقه و چند نوع معامله را پشت‌سرهم یا همزمان اجرا کنید',
            },
            {
                'icon': 'fa-table',
                'title': 'فیلدهای کامل',
                'desc': 'قیمت، ودیعه، اجاره، متراژ، اتاق، آدرس، مختصات، امکانات، توضیحات و لینک',
            },
            {
                'icon': 'fa-images',
                'title': 'مدیریت تصاویر',
                'desc': 'دانلود و ذخیره تصاویر آگهی در کنار فایل داده',
            },
            {
                'icon': 'fa-file-export',
                'title': 'خروجی چندفرمتی',
                'desc': 'Excel، CSV و JSON با نام‌گذاری خودکار بر اساس فیلترها',
            },
            {
                'icon': 'fa-arrows-rotate',
                'title': 'به‌روزرسانی دوره‌ای',
                'desc': 'اجرای مجدد ربات برای به‌روزرسانی فایلینگ و کشف آگهی‌های جدید',
            },
        ],
        'transaction_types': [
            'فروش مسکونی', 'اجاره مسکونی', 'فروش اداری و تجاری',
            'اجاره اداری و تجاری', 'پروژه‌های ساخت‌وساز', 'زمین و باغ',
        ],
        'extraction_tree': extraction_tree_content(),
        'data_fields': [
            {
                'group': 'اطلاعات پایه',
                'icon': 'fa-file-lines',
                'items': 'عنوان، توضیحات، قیمت، ودیعه، اجاره، تاریخ انتشار',
                'fields': ['عنوان', 'توضیحات', 'قیمت', 'ودیعه', 'اجاره', 'تاریخ انتشار'],
            },
            {
                'group': 'موقعیت',
                'icon': 'fa-location-dot',
                'items': 'شهر، محله، آدرس، عرض و طول جغرافیایی',
                'fields': ['شهر', 'محله', 'آدرس', 'عرض جغرافیایی', 'طول جغرافیایی'],
            },
            {
                'group': 'مشخصات فنی',
                'icon': 'fa-ruler-combined',
                'items': 'متراژ، اتاق، طبقه، سال ساخت، امکانات',
                'fields': ['متراژ', 'اتاق', 'طبقه', 'سال ساخت', 'امکانات'],
            },
            {
                'group': 'متادیتا',
                'icon': 'fa-fingerprint',
                'items': 'نوع آگهی‌دهنده، لینک آگهی، شناسه',
                'fields': ['نوع آگهی‌دهنده', 'لینک آگهی', 'شناسه'],
            },
        ],
        'workspace_integration': [
            {
                'icon': 'fa-chart-pie',
                'title': 'تحلیل بازار',
                'desc': 'میانگین قیمت، توزیع، داده پرت و قیمت هر متر',
                'image': 'images/help-analyze-dashboard.png',
                'image_alt': 'داشبورد تحلیل بازار — میانگین قیمت، نمودار توزیع و قیمت هر متر',
                'accent': 'violet',
            },
            {
                'icon': 'fa-map-location-dot',
                'title': 'نقشه آگهی‌ها',
                'desc': 'نمایش جغرافیایی با تفکیک مشاور و شخصی',
                'image': 'images/help-map-view.png',
                'image_alt': 'نقشه تعاملی آگهی‌ها با تفکیک مشاور و مالک شخصی',
                'accent': 'sky',
            },
            {
                'icon': 'fa-code-compare',
                'title': 'مقایسه فایل‌ها',
                'desc': 'مقایسه دو دوره استخراج و کشف تغییرات بازار',
                'image': 'images/help-compare-files.png',
                'image_alt': 'مقایسه دو فایل استخراج و تغییرات قیمت بین دوره‌ها',
                'accent': 'emerald',
            },
            {
                'icon': 'fa-users',
                'title': 'CRM',
                'desc': 'پیوند آگهی به مخاطب، پیگیری و یادآور — حتی بدون ربات هم رایگان است',
                'image': 'images/help-crm-dashboard.png',
                'image_alt': 'داشبورد CRM — مخاطبین، پیگیری‌ها و خلاصه فعالیت‌ها',
                'accent': 'amber',
            },
        ],
        'faqs': [
            {
                'q': 'آیا با یک لایسنس هم ویندوز و هم اندروید دارم؟',
                'a': 'بله. هر لایسنس یک اسلات ربات ویندوز و یک اسلات اپ اندروید دارد. '
                     'در اندروید با همان حساب میزکار وارد شوید؛ در ویندوز کلید لایسنس را فعال کنید.',
            },
            {
                'q': 'ربات ویندوز چه تفاوتی با اپ اندروید دارد؟',
                'a': 'ربات برای استخراج حجیم، چندمنطقه‌ای و ساخت پوشه output روی PC طراحی شده. '
                     'اپ اندروید برای CRM موبایل، اعلان تطبیق ملک، استخراج سبک محله‌ای '
                     'و کار روزانه در مسیر مناسب است.',
            },
            {
                'q': 'ربات دقیقاً چه کاری انجام می‌دهد؟',
                'a': 'ربات روی ویندوز اجرا می‌شود، به دیوار متصل می‌شود و آگهی‌های املاک را '
                     'طبق فیلترهای شما استخراج می‌کند. نتیجه در پوشه output '
                     'به‌صورت فایل‌های Excel/CSV ذخیره می‌شود.',
            },
            {
                'q': 'فایلینگ چگونه روی سیستم من ساخته می‌شود؟',
                'a': 'ربات پوشه output را با ساختار استان/شهر/محله می‌سازد. هر فایل '
                     'مربوط به یک نوع معامله (مثلاً فروش آپارتمان) در همان مسیر قرار می‌گیرد. '
                     'در اپ اندروید فایل‌ها در بخش فایلینگ اپ و میزکار هم دیده می‌شوند.',
            },
            {
                'q': 'چطور داده‌ها را در میزکار ببینم؟',
                'a': 'پس از فعال‌سازی لایسنس، پوشه output را در میزکار آپلود کنید '
                     'یا از اپ اندروید مستقیم به داده‌های همگام‌شده دسترسی داشته باشید.',
            },
            {
                'q': 'آیا CRM بدون خرید لایسنس هم کار می‌کند؟',
                'a': 'بله. مدیریت مخاطبین، املاک شخصی و یادآورها رایگان است. '
                     'خرید لایسنس برای استخراج دیوار و تحلیل پیشرفته لازم است.',
            },
        ],
    }


def license_guide_content():
    """راهنمای ساده فعال‌سازی — زبان روزمره مشاور املاک."""
    return {
        'hero': {
            'eyebrow': 'راهنمای فعال‌سازی',
            'title': 'لایسنس را چطور فعال کنم؟',
            'lead': (
                'بعد از خرید، کلید لایسنس در داشبورد شما آماده است. '
                'می‌توانید همزمان از اپ اندروید و ربات ویندوز استفاده کنید — '
                'در اندروید فقط وارد شوید؛ در ویندوز کلید را در ربات بچسبانید.'
            ),
            'highlights': [
                {'icon': 'fa-clock', 'text': 'حدود ۵ دقیقه تا فعال‌سازی'},
                {'icon': 'fa-mobile-screen', 'text': 'اندروید + ویندوز با یک لایسنس'},
                {'icon': 'fa-shield-halved', 'text': 'پشتیبانی در تمام مراحل'},
            ],
        },
        # url خالی = ویدیوی پیش‌فرض media/Video/ROBOT-INSTALLING.mp4
        # embed: 'https://www.youtube.com/embed/VIDEO_ID'
        # media: 'Video/custom.mp4'
        'video': {
            'title': 'آموزش ویدیویی نصب و فعال‌سازی',
            'subtitle': 'از خرید تا اولین استخراج — گام‌به‌گام',
            'url': '',
            'poster': '',
            'duration': '~۵ دقیقه',
        },
        'flow': [
            {'icon': 'fa-cart-shopping', 'decor_icon': 'coins', 'label': 'خرید لایسنس', 'desc': 'کلید در داشبورد'},
            {'icon': 'fa-mobile-screen', 'decor_icon': 'sparkles', 'label': 'ورود به اپ / ربات', 'desc': 'اندروید یا ویندوز'},
            {'icon': 'fa-chart-line', 'decor_icon': 'download', 'label': 'استخراج و فایلینگ', 'desc': 'دیوار → میزکار'},
        ],
        'steps': [
            {
                'num': '۱',
                'title': 'خرید کنید و کلید را از داشبورد بردارید',
                'icon': 'fa-cart-shopping',
                'decor_icon': 'coins',
                'desc': (
                    'پلن مناسب را انتخاب و پرداخت کنید — می‌توانید با پلن آزمایشی یک‌هفته‌ای '
                    'محصول را امتحان کنید. بلافاصله پس از پرداخت، '
                    'در داشبورد وب بخش «لایسنس‌ها» کلید شما نمایش داده می‌شود. '
                    'کلید را کپی کنید — برای ویندوز لازم است؛ برای اندروید نیازی به وارد کردن کلید نیست.'
                ),
                'tip': 'هر لایسنس شامل یک ربات ویندوز و یک اپ اندروید است.',
            },
            {
                'num': '۲',
                'title': 'اپ اندروید: فقط وارد شوید',
                'icon': 'fa-mobile-screen',
                'decor_icon': 'sparkles',
                'desc': (
                    'اپ دیوار فایلینگ را نصب کنید و با همان نام کاربری و رمز داشبورد وارد شوید. '
                    'دستگاه شما خودکار ثبت می‌شود و استخراج، فایلینگ و CRM فعال می‌شود. '
                    'نیازی به کپی کلید یا شناسه سخت‌افزار نیست.'
                ),
                'tip': 'اگر تازه خریده‌اید، یک‌بار از اپ خارج و دوباره وارد شوید.',
            },
            {
                'num': '۳',
                'title': 'ربات ویندوز: کلید را بچسبانید',
                'icon': 'fa-key',
                'decor_icon': 'rocket',
                'desc': (
                    'ربات را از داشبورد دانلود و نصب کنید. در اولین اجرا کلید لایسنس را '
                    'از داشبورد کپی کرده و در ربات بچسبانید و «فعال‌سازی» را بزنید. '
                    'شناسه سخت‌افزار خودکار ثبت می‌شود — نیازی به ثبت دستی در سایت نیست.'
                ),
                'tip': 'ویندوز ۱۰ یا ۱۱. می‌توانید همزمان با اپ اندروید از همان لایسنس استفاده کنید.',
            },
            {
                'num': '۴',
                'title': 'استخراج را شروع کنید',
                'icon': 'fa-cloud-upload-alt',
                'decor_icon': 'upload',
                'desc': (
                    'در اپ اندروید یا ربات ویندوز شهر و فیلترها را انتخاب کنید و استخراج را بزنید. '
                    'فایل‌ها در بخش فایلینگ اپ یا میزکار وب در دسترس هستند.'
                ),
                'tip': 'برای به‌روزرسانی آگهی‌ها، دوباره استخراج کنید.',
            },
        ],
        'notes': [
            {
                'icon': 'fa-desktop',
                'text': 'هر لایسنس شامل یک ربات ویندوز و یک اپ اندروید است. برای جابه‌جایی دستگاه، از ربات غیرفعال کنید یا در داشبورد اسلات را مدیریت کنید.',
            },
            {
                'icon': 'fa-wifi',
                'text': 'برای کشیدن آگهی‌ها از دیوار و فعال‌سازی لایسنس، اینترنت پایدار لازم است.',
            },
            {
                'icon': 'fa-address-book',
                'text': 'دفترچه مشتریان و املاک (CRM) رایگان است — حتی اگر هنوز ربات نخریده‌اید.',
            },
        ],
        'faq': [
            {
                'q': 'کلید را زدم ولی میزکار هنوز قفل است',
                'a': 'اول در ربات مطمئن شوید پیام «فعال شد» آمده. در اپ اندروید یک‌بار خارج و با همان حساب وارد شوید. '
                     'در داشبورد وضعیت لایسنس باید «فعال» باشد — صفحه را رفرش کنید.',
            },
            {
                'q': 'فایل اکسل کجا ذخیره می‌شود؟',
                'a': 'معمولاً داخل پوشه نصب ربات، در پوشه‌ای به نام output. '
                     'داخلش بر اساس شهر و محله مرتب شده — مثلاً شیراز / معالی‌آباد / فروش آپارتمان.',
            },
            {
                'q': 'می‌خواهم روی لپ‌تاپ دوم هم نصب کنم',
                'a': 'هر لایسنس یک ربات ویندوز و یک اپ اندروید دارد. برای لپ‌تاپ ویندوز دوم، '
                     'ابتدا از کامپیوتر اول غیرفعال کنید یا پلن چندسیستمی بخرید.',
            },
            {
                'q': 'فقط اپ اندروید می‌خواهم — باید ربات ویندوز هم نصب کنم؟',
                'a': 'خیر. پس از خرید، فقط اپ را نصب کنید و با همان حساب داشبورد وارد شوید. '
                     'استخراج، فایلینگ و CRM در اپ فعال می‌شود. ربات ویندوز اختیاری است.',
            },
            {
                'q': 'می‌خواهم همزمان اندروید و ویندوز داشته باشم',
                'a': 'بله — هر لایسنس یک اسلات اندروید و یک اسلات ویندوز دارد. '
                     'در اپ با همان حساب وارد شوید و در ویندوز کلید را در ربات فعال کنید.',
            },
        ],
    }


def app_download_hub_content():
    """متن و ساختار سکشن مرکز دانلود — در راهنما، داشبورد و پرداخت."""
    return {
        'kicker': 'مرکز دانلود',
        'title': 'ربات ویندوز و اپ اندروید',
        'lead': (
            'برای استخراج حرفه‌ای و ساخت بانک فایل، ربات ویندوز توصیه می‌شود؛ '
            'اپ اندروید برای CRM، پیگیری مشتری و کار در محل است. هر دو با یک لایسنس.'
        ),
        'android': {
            'title': 'اپ فایلینگ دیوار',
            'tagline': 'برای موبایل و پیگیری در محل',
            'features': [
                'CRM، مخاطب، معامله و بانک فایل روی گوشی',
                'اعلان تطبیق ملک، یادآور و صف کارهای امروز',
                'استخراج سبک و سریع — مناسب بازدید و میدان',
                'ورود با همان حساب میزکار — بدون کپی کلید',
            ],
            'install_title': 'نصب در ۴ قدم',
            'install_steps': [
                {'num': '۱', 'text': 'APK را دانلود و باز کنید.'},
                {'num': '۲', 'text': 'در صورت نیاز «منابع ناشناخته» را برای مرورگر یا فایل‌منیجر فعال کنید.'},
                {'num': '۳', 'text': 'با همان نام کاربری و رمز میزکار وارد شوید.'},
                {'num': '۴', 'text': 'اعلان‌ها را بپذیرید تا تطبیق ملک و یادآورها را از دست ندهید.'},
            ],
        },
        'windows': {
            'title': 'ربات استخراج دیوار',
            'recommended': True,
            'recommended_label': 'توصیه‌شده',
            'tagline': 'قدرتمندترین ابزار ساخت بانک فایل',
            'features': [
                'استخراج گروهی — چند زیردسته و محله در یک اجرا',
                'سقف تا ۵۰۰ آگهی در هر دسته‌بندی',
                'زمان‌بندی حرفه‌ای و استخراج خودکار در پس‌زمینه',
                'خروجی اکسل، تصاویر و آپلود مستقیم در میزکار',
            ],
            'update_title': 'قبل از به‌روزرسانی یا حذف',
            'update_notes': [
                'از پوشه output کنار ربات (اکسل‌ها و تصاویر استخراج‌شده) یک کپی بگیرید — با حذف یا نصب مجدد، این پوشه ممکن است خالی شود.',
                'استخراج در حال اجرا را متوقف کنید و ربات را کامل ببندید، سپس نصب‌کننده جدید را اجرا کنید.',
                'کلید لایسنس معمولاً حفظ می‌شود؛ در صورت درخواست، همان کلید داشبورد را دوباره وارد کنید.',
            ],
        },
        'play_protect': {
            'title': 'Play Protect',
            'summary': (
                'هشدار «App not recognized» یا «Blocked» برای APK خارج از Play طبیعی است — '
                'به‌معنی ویروس نیست. More details → Install anyway (در MIUI/Samsung: «نصب در هر صورت»).'
            ),
            'why': (
                'اپ از Google Play منتشر نشده و مستقیم از سایت رسمی divarfiling.ir نصب می‌شود. '
                'Play Protect برای APKهای خارج از فروشگاه معمولاً «App not recognized» یا «Blocked» نشان می‌دهد — '
                'این به‌معنی ویروس بودن اپ نیست؛ فقط یعنی گوگل این فایل را در فروشگاه ندیده است.'
            ),
            'cta': 'Install anyway — نصب در هر صورت',
            'cta_hint': 'روی هشدار بزنید → More details → Install anyway (در MIUI/Samsung: «نصب در هر صورت»)',
            'reasons': [
                'اپ با امضای release رسمی تیم فایلینگ دیوار ساخته شده',
                'فقط به سرور امن divarfiling.ir متصل می‌شود',
                'هزاران مشاور املاک با همین روش نصب می‌کنند',
            ],
        },
    }


def product_fake_reviews():
    """نظرات نمایشی — لحن‌های متنوع و طبیعی."""
    return [
        {
            'name': 'املاک صدیقی',
            'initial': 'ص',
            'rating': 5,
            'date': '۳ هفته پیش',
            'content': (
                'دیگه حوصله اسکرول دیوار رو ندارم والا. محله رو انتخاب می‌کنم، '
                'برم چای بخورم، برگردم اکسل آماده‌ست. میزکار هم قیمت‌ها رو برام مرتب می‌کنه.'
            ),
            'is_verified': True,
        },
        {
            'name': 'کاوه نظری',
            'initial': 'ک',
            'rating': 5,
            'date': '۱ ماه پیش',
            'content': (
                'یه مشتری گفت مترش هفتاد تومنه، من لیست هفته قبل رو نشونش دادم — ساکت شد. '
                'همین. نصبش هم تو یه ساعت تموم شد.'
            ),
            'is_verified': True,
        },
        {
            'name': 'آژانس مهر — شیراز',
            'initial': 'م',
            'rating': 5,
            'date': '۱ ماه پیش',
            'content': (
                'سه مشاور، سه محله، سه فایل جدا — هر صبح آپدیت می‌شه. '
                'دیگه مجبور نیستیم یکی کل روز پشت لپ‌تاپ بشینه.'
            ),
            'is_verified': True,
        },
        {
            'name': 'رضا مرادی',
            'initial': 'ر',
            'rating': 5,
            'date': '۲ ماه پیش',
            'content': 'خیلی ممنونیم، واقعاً بدردبخوره و کار راه‌اندازه.',
            'is_verified': False,
        },
        {
            'name': 'دفتر املاک آریا',
            'initial': 'آ',
            'rating': 4,
            'date': '۲ ماه پیش',
            'content': (
                'اول آپلود برام سخت بود، تیم پشتیبانی صبورانه راهنمایی کرد. '
                'الان شنبه‌ها فایل جدید می‌گیریم و با هفته قبل مقایسه می‌کنیم — خیلی به درد جلسه هفتگی می‌خوره.'
            ),
            'is_verified': True,
        },
        {
            'name': 'سمیه گرگانی',
            'initial': 'س',
            'rating': 5,
            'date': '۳ ماه پیش',
            'content': (
                'تازه‌وارد بودم، نمی‌دونستم اینجا آپارتمان چنده. '
                'الان وقتی مالک تماس می‌گیره با عدد جواب می‌دم، نه حدس.'
            ),
            'is_verified': True,
        },
        {
            'name': 'گروه املاک پارس',
            'initial': 'پ',
            'rating': 5,
            'date': '۳ ماه پیش',
            'content': (
                'دو هفته پیش و الان رو کنار هم گذاشتیم — تو دو تا محله افت قیمت مشخص بود. '
                'بدون این ابزار حدس می‌زدیم.'
            ),
            'is_verified': True,
        },
        {
            'name': 'مسعود حیدری',
            'initial': 'ح',
            'rating': 4,
            'date': '۴ ماه پیش',
            'content': (
                'یه ستاره کم گذاشتم چون اولش باید با فیلترها آشنا شی — ولی بعدش؟ '
                'دیگه دستی برنمی‌گردم، قول می‌دم.'
            ),
            'is_verified': False,
        },
    ]


def product_rating_display_stats():
    """آمار نمایشی امتیاز — مستقل از دیتابیس واقعی."""
    total_count = 127
    reviews_count = 84
    average = 4.9
    distribution = {5: 98, 4: 22, 3: 5, 2: 2, 1: 0}
    percentages = {
        value: round((count / total_count) * 100, 1)
        for value, count in distribution.items()
    }
    return {
        'average_rating': average,
        'rating_count': total_count,
        'reviews_count': reviews_count,
        'rating_distribution': distribution,
        'rating_percentages': percentages,
    }


# ضریب نمایش آمار صفحه اصلی (عدد واقعی دیتابیس × این مقدار)
HOME_STATS_DISPLAY_MULTIPLIER = 3
# ضریب اضافه فقط برای «خرید موفق» (×3 روی مقدار قبلی نمایشی)
HOME_STATS_ORDERS_EXTRA_MULTIPLIER = 3
# ضریب اضافه فقط برای «لایسنس فعال» روی مقدار نمایشی (×6 نسبت به raw؛ ×3 نسبت به نمایش قبلی)
HOME_STATS_LICENSES_EXTRA_MULTIPLIER = 6
HOME_STATS_CACHE_KEY = 'shop:home_display_stats:v4'
HOME_STATS_CACHE_TTL = 60  # ثانیه — آمار لایو با کش کوتاه


def _home_satisfaction_rate() -> int:
    """رضایت کاربران از امتیازهای واقعی محصول (درصد ۴ و ۵ ستاره)."""
    from django.db.models import Count, Q

    from shop.models import ProductRating

    agg = ProductRating.objects.aggregate(
        total=Count('id'),
        positive=Count('id', filter=Q(rating__gte=4)),
    )
    total = int(agg['total'] or 0)
    if total < 5:
        # هنوز دادهٔ کافی نیست — میانگین نزدیک به رضایت بالای واقعی بازار
        return 99
    rate = round((int(agg['positive'] or 0) / total) * 100)
    return max(1, min(99, rate))


def _home_uptime_payload(now):
    """زمان کارکرد دقیق سیستم از اولین فعال‌سازی/لایسنس."""
    from accounts.services.admin_dashboard import get_system_start_at
    from django.utils import timezone
    from workspace.services.jalali_input import format_jalali_date, to_persian_digits

    start = get_system_start_at()
    if not start:
        return {
            'uptime_label': None,
            'uptime_started_jalali': None,
            'uptime_days': 0,
            'uptime_hours': 0,
            'uptime_minutes': 0,
            'uptime_total_seconds': 0,
        }

    start_local = timezone.localtime(start) if timezone.is_aware(start) else start
    now_local = timezone.localtime(now) if timezone.is_aware(now) else now
    total_seconds = max(0, int((now_local - start_local).total_seconds()))
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    parts = []
    if days:
        parts.append(f'{days} روز')
    if hours or days:
        parts.append(f'{hours} ساعت')
    parts.append(f'{minutes} دقیقه')

    return {
        'uptime_label': to_persian_digits(' و '.join(parts)),
        'uptime_started_jalali': to_persian_digits(format_jalali_date(start_local)),
        'uptime_days': days,
        'uptime_hours': hours,
        'uptime_minutes': minutes,
        'uptime_total_seconds': total_seconds,
    }


def home_display_stats():
    """آمار لایو صفحه اصلی از دیتابیس؛ شمارنده‌ها با ضریب نمایش."""
    from django.contrib.auth import get_user_model
    from django.core.cache import cache
    from django.db.models import Q
    from django.utils import timezone

    from licenses.models import License
    from shop.models import Order

    cached = cache.get(HOME_STATS_CACHE_KEY)
    if cached is not None:
        return cached

    User = get_user_model()
    now = timezone.now()
    mult = HOME_STATS_DISPLAY_MULTIPLIER

    users_raw = User.objects.filter(is_active=True).count()
    orders_raw = Order.objects.filter(status='paid').count()
    licenses_raw = License.objects.filter(status='active').filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    ).count()

    uptime = _home_uptime_payload(now)

    stats = {
        'total_users': users_raw * mult,
        'total_orders': orders_raw * mult * HOME_STATS_ORDERS_EXTRA_MULTIPLIER,
        'total_licenses': licenses_raw * mult * HOME_STATS_LICENSES_EXTRA_MULTIPLIER,
        'satisfaction_rate': _home_satisfaction_rate(),
        'is_live': True,
        'display_multiplier': mult,
        'raw': {
            'total_users': users_raw,
            'total_orders': orders_raw,
            'total_licenses': licenses_raw,
        },
        **uptime,
    }
    cache.set(HOME_STATS_CACHE_KEY, stats, HOME_STATS_CACHE_TTL)
    return stats


def _format_toman_compact(amount: int) -> str:
    """نمایش فشرده قیمت به فارسی — مثلاً ۲۵۰ هزار یا ۲.۵ میلیون."""
    if amount >= 1_000_000:
        whole = amount // 1_000_000
        remainder = amount % 1_000_000
        if remainder and remainder % 100_000 == 0:
            return f'{whole}٫{remainder // 100_000} میلیون'
        return f'{whole} میلیون'
    thousands = amount // 1_000
    formatted = f'{thousands:,}'.replace(',', '،')
    return f'{formatted} هزار'


def _home_pricing_tiers() -> list[dict]:
    """کارت‌های قیمت صفحه اصلی — همگام با bot_license_plans."""
    plans = bot_license_plans()
    daily = next(
        p for p in plans
        if p['plan_type'] == 'daily' and not p.get('allow_bulk_purchase')
    )
    monthly = next(p for p in plans if p['plan_type'] == 'monthly' and p['order'] == 1)
    daily_marketing = bot_plan_marketing_by_key()[('daily', False, 0)]

    daily_price = _format_toman_compact(daily['price'])
    monthly_price = _format_toman_compact(monthly['price'])

    return [
        {
            'id': 'free',
            'icon': 'fa-gift',
            'decor_icon': 'layers',
            'title': 'میزکار رایگان',
            'price': '۰',
            'price_note': 'تومان — برای همیشه',
            'badge': 'شروع فوری',
            'accent': 'emerald',
            'features': [
                'CRM کامل: مخاطبین، معاملات و فایل‌های شخصی',
                'صف امروز، یادآور، تقویم و قالب پیام',
                'مدیریت تیم آژانس و اتوماسیون پیگیری',
            ],
            'cta_label': 'ثبت‌نام رایگان',
            'cta_icon': 'fa-user-plus',
        },
        {
            'id': 'pro',
            'icon': 'fa-robot',
            'decor_icon': 'rocket',
            'title': 'لایسنس ربات',
            'price': daily_price,
            'price_note': 'تومان / آزمایش ۷ روزه',
            'price_hint': f'پلن ماهانه از {monthly_price} تومان',
            'badge': 'استخراج + تحلیل',
            'accent': 'violet',
            'features': [
                daily_marketing['features'][0]['text'],
                daily_marketing['features'][1]['text'],
                'استخراج دیوار، فایلینگ، تحلیل چندلایه و نقشه Pro',
                daily_marketing['features'][5]['text'],
            ],
            'cta_label': 'مشاهده پلن‌ها',
            'cta_icon': 'fa-tags',
        },
    ]


def home_page_content():
    """محتوای صفحه اصلی — فایلینگ دیوار."""
    return {
        'hero': {
            'eyebrow': 'سیستم‌عامل مشاوران حرفه‌ای املاک',
            'title_prefix': 'جایی که ',
            'title_brand': 'فرصت‌ها…',
            'title_suffix': '',
            'title_line2': 'به معامله تبدیل می‌شوند.',
            'title': 'جایی که فرصت‌ها… به معامله تبدیل می‌شوند.',
            'subtitle': (
                'از پیدا کردن فایل مناسب تا شناخت مشتری، پیگیری، تطبیق هوشمند و تحلیل بازار؛ '
                'همه ابزارهای روزانه یک مشاور املاک در یک میزکار.'
            ),
            'subtitle_secondary': (
                'میزکار وب برای CRM و فایلینگ — ربات ویندوز برای استخراج و تحلیل عمیق، هر زمان که نیاز داشتی.'
            ),
            'trust_items': [
                'شروع رایگان',
                'CRM رایگان',
                'مخصوص بازار املاک ایران',
            ],
            'cta_primary_label': 'ورود به میزکار',
            'cta_primary_icon': 'fa-layer-group',
            'cta_guest_label': 'شروع رایگان',
            'cta_guest_icon': 'fa-rocket',
            'cta_secondary_label': 'ببین چطور کار می‌کند',
            'cta_secondary_icon': 'fa-arrow-down',
            'cta_bot_label': 'فعال‌سازی ربات استخراج',
            'cta_bot_icon': 'fa-robot',
        },
        'intro_video_section': {
            'kicker': 'معرفی محصول',
            'title': 'فایلینگ دیوار دقیقاً چه کاری انجام می‌دهد؟',
            'lead': (
                'در کمتر از دو دقیقه ببین چطور از فایل‌های پراکنده، مشتری‌ها و پیگیری‌ها '
                'یک جریان کاری منظم می‌سازد.'
            ),
        },
        'story_hook': {
            'kicker': 'روایت یک روز',
            'title': 'از چالش تا راه‌حل — در یک میزکار',
            'subtitle': 'هر مرحله: درد واقعی مشاور → ابزار در میزکار → نتیجه قابل حس',
        },
        'story_scenes': [
            {
                'step': '01',
                'title': 'دنبال فایل مالک بودی؟',
                'pain': 'بین ده‌ها آگهی دنبال فایل واقعی می‌گردی',
                'solution': 'تشخیص و فیلتر فایل مناسب',
                'solution_badge': 'سیگنال آگهی‌دهنده',
                'pain_image': 'images/story-owner-search.webp',
                'solution_image': 'images/story-owner-search-rahkar.webp',
                'accent': 'violet',
            },
            {
                'step': '02',
                'title': 'مشتری منتظره',
                'pain': 'نیاز مشتری بین دفتر، اکسل و واتساپ گم می‌شود',
                'solution': 'CRM + پیشنهاد فایل مناسب',
                'solution_badge': 'تطبیق هوشمند',
                'pain_image': 'images/story-customer-office.webp',
                'solution_image': 'images/story-customer-office-rahkar.webp',
                'accent': 'sky',
            },
            {
                'step': '03',
                'title': 'یادت رفت تماس بگیری',
                'pain': 'یک پیگیری فراموش‌شده می‌تواند یک معامله را از بین ببرد',
                'solution': 'یادآوری + صف کار امروز',
                'solution_badge': 'صف امروز',
                'pain_image': 'images/story-followup-missed.webp',
                'solution_image': 'images/story-followup-missed-rahkar.webp',
                'accent': 'amber',
            },
            {
                'step': '04',
                'title': 'فایل داری ولی پیداش نمی‌کنی',
                'pain': 'فایل‌ها زیاد شده‌اند اما پیدا کردن فایل مناسب زمان می‌برد',
                'solution': 'جستجوی هوشمند و فیلتر',
                'solution_badge': 'فیلتر پیشرفته',
                'pain_image': 'images/story-files-chaos.webp',
                'solution_image': 'images/story-files-chaos-rahkar.webp',
                'accent': 'rose',
            },
            {
                'step': '05',
                'title': 'فایل‌ها سرمایه تو هستند',
                'pain': 'اطلاعات مشتری و فایل نباید بدون کنترل در دسترس همه باشد',
                'solution': 'سطح دسترسی · مدیریت تیم · امنیت اطلاعات',
                'solution_badge': 'کنترل دسترسی',
                'pain_image': 'images/story-security-vault.webp',
                'solution_image': 'images/story-security-vault-rahkar.webp',
                'accent': 'emerald',
            },
        ],
        'story_climax': {
            'time': 'آخر شب',
            'title': 'امروز واقعاً فروختی؟',
            'subtitle': 'یا فقط دنبال فایل بودی؟',
            'line': 'کار اصلی تو فروش است — نه جستجو.',
            'image': 'images/help-workspace-home.png',
            'image_alt': 'داشبورد میزکار فایلینگ دیوار',
        },
        'before_after': {
            'title': 'وقتشه روش کارت را عوض کنی',
            'subtitle': 'همان کار روزانه — با جریان شفاف‌تر و کمتر فراموشی',
            'before_label': 'روش قدیمی',
            'after_label': 'فایلینگ دیوار',
            'before_stack': [
                {'icon': 'fa-book', 'text': 'دفتر و یادداشت'},
                {'icon': 'fa-file-excel', 'text': 'Excel پراکنده'},
                {'icon': 'fa-brands fa-whatsapp', 'text': 'واتساپ و تماس'},
                {'icon': 'fa-search', 'text': 'جستجوی دستی'},
            ],
            'after_stack': [
                {'icon': 'fa-layer-group', 'text': 'فایلینگ منظم'},
                {'icon': 'fa-users', 'text': 'CRM املاک'},
                {'icon': 'fa-list-check', 'text': 'صف امروز'},
                {'icon': 'fa-wand-magic-sparkles', 'text': 'تطبیق و اتوماسیون'},
            ],
            'pairs': [
                {
                    'before': 'جستجوی چندساعته بین آگهی‌ها',
                    'after': 'رسیدن سریع‌تر به فایل‌های مناسب',
                },
                {
                    'before': 'دفتر + Excel + WhatsApp',
                    'after': 'یک میزکار یکپارچه',
                },
                {
                    'before': 'پیگیری فراموش‌شده',
                    'after': 'یادآوری و صف امروز',
                },
                {
                    'before': 'نیاز مشتری گم می‌شود',
                    'after': 'تطبیق فایل نزدیک به خواسته',
                },
            ],
        },
        'intelligence_section': {
            'kicker': 'هوش مصنوعی',
            'title_lead': 'هوش مصنوعی',
            'title_rest': 'داخل جریان کار شماست',
            'subtitle': (
                'ثبت سریع‌تر، تطبیق دقیق‌تر و خلاصه‌های هوشمندتر برای تصمیم‌های بهتر در املاک.'
            ),
            'panels': [
                {
                    'id': 'voice',
                    'icon': 'fa-microphone-lines',
                    'title': 'فرمان هوشمند و صوتی',
                    'desc': 'لازم نیست همیشه تایپ کنی؛ مخاطب، فایل شخصی و یادآوری را با جملهٔ طبیعی ثبت کن.',
                    'chips': ['ثبت فایل جدید', 'یادآوری تماس', 'جستجوی فایل'],
                    'demos': [
                        {
                            'command': 'برای فردا ساعت ۱۰ یادآوری تماس با رضایی ثبت کن',
                            'result': 'یادآوری آماده ثبت است',
                            'result_detail': 'فردا · ساعت ۱۰:۰۰ · تماس با رضایی',
                            'result_icon': 'fa-bell',
                        },
                        {
                            'command': 'یک خریدار آپارتمان ۸۰ تا ۱۰۰ متر در سعادت‌آباد ثبت کن',
                            'result': 'پیش‌نمایش مخاطب آماده است',
                            'result_detail': 'خریدار · سعادت‌آباد · ۸۰–۱۰۰ متر',
                            'result_icon': 'fa-user-plus',
                        },
                    ],
                },
                {
                    'id': 'matching',
                    'icon': 'fa-house-circle-check',
                    'title': 'تطبیق هوشمند',
                    'desc': 'نیاز مشتری را ثبت کن؛ سیستم فایل‌های نزدیک‌تر به بودجه، متراژ و محله را پیشنهاد می‌دهد.',
                    'customer': {
                        'name': 'خریدار — سعادت‌آباد',
                        'need': 'آپارتمان ۸۰–۱۰۰ متر · فروش',
                    },
                    'matches_title': 'پیشنهادهای تطبیق',
                    'matches': [
                        {
                            'tier': 'high',
                            'tier_label': 'تطبیق بالا',
                            'meta': 'آپارتمان ۸۵ متر · سعادت‌آباد',
                            'price': '۴,۲ میلیارد',
                        },
                        {
                            'tier': 'good',
                            'tier_label': 'مناسب',
                            'meta': 'آپارتمان ۹۵ متر · سعادت‌آباد',
                            'price': '۴,۸ میلیارد',
                        },
                        {
                            'tier': 'near',
                            'tier_label': 'نزدیک',
                            'meta': 'آپارتمان ۷۸ متر · سعادت‌آباد',
                            'price': '۳,۹ میلیارد',
                        },
                    ],
                },
                {
                    'id': 'summary',
                    'icon': 'fa-folder-open',
                    'title': 'خلاصه هوشمند فایل',
                    'desc': 'اطلاعات زیاد را سریع‌تر بخوان؛ نکات مهم فایل را در یک خلاصه ساختاریافته ببین.',
                    'raw_label': 'داده خام فایل',
                    'raw_lines': [
                        'آپارتمان ۸۵ متری · فروش · ۴,۵ میلیارد',
                        'نوساز، پارکینگ، انباری، طبقه ۳',
                        'سعادت‌آباد · مالک · ۲ خواب',
                    ],
                    'summary_label': 'خلاصه هوشمند',
                    'summary_bullets': [
                        {
                            'icon': 'fa-coins',
                            'title': 'قیمت در محدوده رایج',
                            'desc': 'هم‌متراژ همین محله',
                        },
                        {
                            'icon': 'fa-user-check',
                            'title': 'مالک واقعی',
                            'desc': 'مناسب پیشنهاد مستقیم',
                        },
                        {
                            'icon': 'fa-people-roof',
                            'title': 'نوساز با پارکینگ',
                            'desc': 'نقطه قوت برای خریدار خانواده',
                        },
                    ],
                },
            ],
        },
        'product_flow': {
            'kicker': 'جریان کار',
            'title': 'از استخراج تا معامله',
            'subtitle': 'مسیر فایل از دیوار تا قرارداد — در یک خط پیوسته',
            'steps': [
                {
                    'icon': 'fa-robot',
                    'title': 'استخراج',
                    'desc': 'فایل‌ها را پیدا کن',
                    'detail': 'ربات استخراج، آگهی‌های مرتبط دیوار را خودکار وارد میزکار می‌کند — بدون جستجوی دستی چندساعته.',
                    'accent': 'violet',
                },
                {
                    'icon': 'fa-database',
                    'title': 'فایلینگ',
                    'desc': 'مرتب و فیلتر کن',
                    'detail': 'فایل‌ها با ساختار استان، شهر و محله سازماندهی می‌شوند؛ فیلتر مالک، مشاور و نوع ملک همیشه آماده است.',
                    'accent': 'indigo',
                },
                {
                    'icon': 'fa-chart-line',
                    'title': 'تحلیل',
                    'desc': 'بازار را بفهم',
                    'detail': 'قیمت متر، روند بازار و مقایسه دوره‌ای — قبل از پیشنهاد قیمت یا مذاکره، تصویر واقعی بازار را ببینید.',
                    'accent': 'emerald',
                },
                {
                    'icon': 'fa-arrows-left-right',
                    'title': 'تطبیق',
                    'desc': 'فایل را به مشتری وصل کن',
                    'detail': 'بر اساس بودجه، متراژ، محله و نوع معامله — فایل‌های نزدیک‌تر به نیاز ثبت‌شده را ببین و سریع‌تر پیشنهاد بده.',
                    'accent': 'sky',
                },
                {
                    'icon': 'fa-users',
                    'title': 'CRM',
                    'desc': 'مشتری را پیگیری کن',
                    'detail': 'سرنخ تا قرارداد در قیف معاملات؛ صف کار امروز و یادآوری پیگیری — هیچ تماسی در مسیر فروش گم نمی‌شود.',
                    'accent': 'violet',
                },
                {
                    'icon': 'fa-handshake',
                    'title': 'معامله',
                    'desc': 'فرصت را به قرارداد تبدیل کن',
                    'detail': 'فایل مناسب به مشتری درست وصل می‌شود — از اولین تماس تا امضای قرارداد، همه‌چیز در یک خط پیوسته.',
                    'accent': 'amber',
                },
            ],
        },
        'product_pillars_section': {
            'kicker': 'اکوسیستم محصول',
            'title': 'هر ماژول برای یک نتیجهٔ واقعی',
            'subtitle': 'از فایلینگ و CRM تا تحلیل، نقشه، تطبیق و مدیریت آژانس — در یک Design System واحد',
        },
        'product_ecosystem': [
            {
                'id': 'crm',
                'size': 'hero',
                'accent': 'violet',
                'icon': 'fa-users',
                'title': 'CRM املاک',
                'outcome': 'مشتری را از سرنخ تا قرارداد — بدون فراموشی تماس',
                'image': 'images/help-crm-dashboard.png',
                'benefits': ['قیف وضعیت و صف امروز', 'تطبیق فایل با نیاز مشتری'],
                'landing_url_name': 'seo_landing_real_estate_crm',
            },
            {
                'id': 'filing',
                'size': 'wide',
                'accent': 'indigo',
                'icon': 'fa-layer-group',
                'title': 'فایلینگ هوشمند',
                'outcome': 'فایل مناسب را سریع‌تر پیدا کن',
                'image': 'images/help-map-view.png',
                'benefits': ['فیلتر مالک و محله', 'جستجوی پیشرفته'],
                'landing_slug': 'filing',
            },
            {
                'id': 'market',
                'size': 'tall',
                'accent': 'emerald',
                'icon': 'fa-chart-line',
                'title': 'تحلیل بازار',
                'outcome': 'قبل از مذاکره، بازار را ببین',
                'image': 'images/help-analyze-dashboard.png',
                'benefits': ['قیمت متر و روند', 'گزارش چندلایه'],
                'landing_slug': 'market-intelligence',
            },
            {
                'id': 'map',
                'size': 'compact',
                'accent': 'sky',
                'icon': 'fa-map',
                'title': 'نقشه Pro',
                'outcome': 'موقعیت فایل‌ها روی محله',
                'image': 'images/help-map-view.png',
                'benefits': ['خوشه‌بندی و فیلتر'],
            },
            {
                'id': 'automation',
                'size': 'compact',
                'accent': 'rose',
                'icon': 'fa-robot',
                'title': 'اتوماسیون',
                'outcome': 'پیگیری خودکار مخاطب راکد',
                'image': 'images/help-crm-today.png',
                'benefits': ['قوانین و یادآور'],
            },
            {
                'id': 'team',
                'size': 'compact',
                'accent': 'amber',
                'icon': 'fa-users-gear',
                'title': 'مدیریت آژانس',
                'outcome': 'تیم، دسترسی و عملکرد',
                'image': 'images/help-crm-team.png',
                'benefits': ['تخصیص و اشتراک فایل'],
            },
            {
                'id': 'personal',
                'size': 'compact',
                'accent': 'cyan',
                'icon': 'fa-building',
                'title': 'فایل شخصی',
                'outcome': 'املاک تحت مدیریت تو',
                'image': 'images/help-crm-deals.png',
                'benefits': ['جزئیات و پیگیری'],
            },
            {
                'id': 'calendar',
                'size': 'compact',
                'accent': 'teal',
                'icon': 'fa-calendar',
                'title': 'تقویم و یادآور',
                'outcome': 'قرارها در یک نما',
                'image': 'images/help-crm-today.png',
                'benefits': ['یادآوری تماس'],
            },
        ],
        'product_pillars': [
            {
                'id': 'filing',
                'title': 'فایلینگ هوشمند',
                'nav_icon': 'fa-layer-group',
                'outcome': 'فایل مناسب را سریع پیدا کن — نه بعد از ساعت‌ها جستجو',
                'image': 'images/help-map-view.png',
                'accent': 'indigo',
                'landing_slug': 'filing',
                'features': [
                    'فیلتر مالک و مشاور',
                    'جستجوی پیشرفته',
                    'ساختار استان / شهر / محله',
                ],
            },
            {
                'id': 'crm',
                'title': 'CRM املاک',
                'nav_icon': 'fa-users',
                'outcome': 'مشتری را از سرنخ تا قرارداد — بدون فراموشی',
                'image': 'images/help-crm-dashboard.png',
                'accent': 'violet',
                'landing_url_name': 'seo_landing_real_estate_crm',
                'features': [
                    'قیف وضعیت',
                    'صف کار امروز',
                    'تطبیق فایل و مشتری',
                ],
            },
            {
                'id': 'market',
                'title': 'تحلیل بازار',
                'nav_icon': 'fa-chart-pie',
                'outcome': 'بازار را ببین — قبل از اینکه رقیب جلو بزند',
                'image': 'images/help-analyze-dashboard.png',
                'accent': 'emerald',
                'landing_slug': 'market-intelligence',
                'features': [
                    'گزارش چندلایه',
                    'قیمت متر و روند',
                    'مقایسه دوره‌ای',
                ],
            },
        ],
        'extra_chips': [
            {'label': 'اتوماسیون', 'icon': 'fa-robot'},
            {'label': 'نقشه Pro', 'icon': 'fa-map'},
            {'label': 'تقویم', 'icon': 'fa-calendar'},
            {'label': 'Compare', 'icon': 'fa-scale-balanced'},
            {'label': 'مدیریت تیم', 'icon': 'fa-users-gear'},
            {'label': 'اشتراک فایل', 'icon': 'fa-share-nodes'},
        ],
        'pricing_section': {
            'title': 'انتخاب مسیر شروع',
            'subtitle': 'CRM میزکار رایگان است — لایسنس ربات برای استخراج، فایلینگ و تحلیل',
        },
        'pricing_tiers': _home_pricing_tiers(),
        'visual_gallery': {
            'kicker': 'در عمل ببینید',
            'title': 'میزکار واقعی، نه وعده روی کاغذ',
            'desc': 'هر ماژول با اسکرین‌شات واقعی — از CRM تا نقشه و ابزارهای کارشناسی',
            'items': [
                {
                    'image': 'images/help-workspace-home.png',
                    'caption': 'نمای کلی میزکار',
                    'accent': 'violet',
                    'size': 'wide',
                },
                {
                    'image': 'images/help-crm-deals.png',
                    'caption': 'قیف معاملات',
                    'accent': 'rose',
                    'size': 'normal',
                },
                {
                    'image': 'images/help-analyze-dashboard.png',
                    'caption': 'تحلیل قیمت محله',
                    'accent': 'amber',
                    'size': 'normal',
                },
                {
                    'image': 'images/help-map-view.png',
                    'caption': 'نقشه تعاملی Pro',
                    'accent': 'sky',
                    'size': 'wide',
                },
                {
                    'image': 'images/help-compare-files.png',
                    'caption': 'مقایسه دوره‌ای',
                    'accent': 'cyan',
                    'size': 'normal',
                },
                {
                    'image': 'images/help-tools-panel.png',
                    'caption': 'ابزارهای هوشمند',
                    'accent': 'amber',
                    'size': 'normal',
                },
                {
                    'image': 'images/help-crm-today.png',
                    'caption': 'صف کار امروز',
                    'accent': 'emerald',
                    'size': 'normal',
                },
                {
                    'image': 'images/help-bot-extract-tab.png',
                    'caption': 'ربات استخراج',
                    'accent': 'indigo',
                    'size': 'normal',
                },
            ],
        },
        'team_section': {
            'kicker': 'تیم و آژانس',
            'title': 'مدیریت آژانس، نه فقط یک مشاور',
            'desc': (
                'اعضای تیم، تخصیص مشتری، ماتریس عملکرد، همگام‌سازی و وب‌هوک — '
                'برای آژانس‌هایی که می‌خواهند همه چیز زیر یک سقف باشد.'
            ),
            'image': 'images/help-crm-team.png',
            'features': [
                {'icon': 'fa-users-gear', 'title': 'مدیریت اعضا', 'desc': 'دعوت، نقش و دسترسی هر مشاور'},
                {'icon': 'fa-chart-simple', 'title': 'ماتریس عملکرد', 'desc': 'تماس، بازدید، معامله — امتیاز هر عضو'},
                {'icon': 'fa-share-nodes', 'title': 'اشتراک فایل', 'desc': 'تخصیص و انتقال ملک بین مشاوران'},
                {'icon': 'fa-plug', 'title': 'وب‌هوک و Sync', 'desc': 'ورود سرنخ از سایت یا CRM خارجی'},
            ],
            'metrics': [
                {'value': '۳+', 'label': 'عضو تیم'},
                {'value': '۱۰۰٪', 'label': 'شفافیت عملکرد'},
                {'value': 'رایگان', 'label': 'در CRM'},
            ],
        },
        'education_cta': {
            'kicker': 'آموزش',
            'title': 'از صفر تا حرفه‌ای — گام‌به‌گام',
            'desc': 'راهنمای تصویری نصب ربات، آپلود فایل، تحلیل بازار و CRM پیشرفته',
            'image': 'images/help-bot-install.png',
            'steps_count': '۲۵+',
            'topics': ['نصب ربات', 'فایلینگ', 'تحلیل', 'CRM', 'تیم'],
            'academy_label': 'ویدیوهای آکادمی',
        },
        'nationwide': {
            'kicker': 'پوشش سراسری',
            'title': 'در تمام ایران کار می‌کند',
            'desc': (
                'هر شهری که در دیوار صفحه اختصاصی دارد — از تهران تا شهرهای کوچک — '
                'ربات می‌تواند آگهی‌ها را استخراج و در ساختار استان / شهر / محله ذخیره کند.'
            ),
            'points': [
                {'icon': 'fa-map', 'decor_icon': 'map_pin', 'title': '۳۱ استان', 'desc': 'پوشش تمام استان‌های کشور'},
                {'icon': 'fa-city', 'decor_icon': 'layers', 'title': 'هر شهر فعال', 'desc': 'هر جایی که دیوار آگهی دارد'},
                {'icon': 'fa-folder', 'decor_icon': 'clipboard_list', 'title': 'فایلینگ منظم', 'desc': 'ساختار استان / شهر / محله'},
            ],
            'cities': [
                'تهران', 'مشهد', 'اصفهان', 'شیراز', 'تبریز', 'اهواز', 'کرج', 'قم',
                'رشت', 'یزد', 'کرمان', 'ارومیه', 'زاهدان', 'همدان', 'کرمانشاه',
                'اراک', 'بندرعباس', 'گرگان', 'ساری', 'قزوین', 'سنندج', 'بیرجند',
                'خرم‌آباد', 'یاسوج', 'ایلام', 'بوشهر', 'زنجان', 'شهرکرد', 'سمنان',
            ],
        },
        'showcase_slides': [
            {
                'accent': 'violet',
                'icon': 'fa-chart-pie',
                'eyebrow': 'CRM حرفه‌ای',
                'title': 'قیف فروش، پیگیری و اتوماسیون',
                'desc': 'مخاطبین، معاملات، صف کار روزانه، یادآور، قالب پیام و قوانین خودکار — همه در یک داشبورد.',
                'visual': 'crm',
                'image': 'images/help-crm-dashboard.png',
            },
            {
                'accent': 'violet',
                'icon': 'fa-layer-group',
                'eyebrow': 'میزکار',
                'title': 'مرکز فرمان یکپارچه',
                'desc': 'نمای کلی هوشمند با شاخص‌های زنده، قیف وضعیت و دسترسی سریع به همه ماژول‌ها.',
                'visual': 'workspace',
                'image': 'images/help-workspace-home.png',
            },
            {
                'accent': 'sky',
                'icon': 'fa-chart-line',
                'eyebrow': 'تحلیل بازار',
                'title': 'گزارش چندلایه با عمق بازار',
                'desc': 'میانگین قیمت، قیمت متر، پرت‌ها، روند، اعتماد تحلیل و نگاه سریع سطح ۱ تا ۳.',
                'visual': 'analytics',
                'image': 'tahlil-daghigh.png',
            },
            {
                'accent': 'emerald',
                'icon': 'fa-map-location-dot',
                'eyebrow': 'نقشه Pro',
                'title': 'نقشه تعاملی حرفه‌ای',
                'desc': 'خوشه‌بندی، فیلتر پیشرفته، لایه‌های basemap، خروجی تصویر و پاپ‌آپ غنی آگهی.',
                'visual': 'map',
                'image': 'images/help-map-view.png',
            },
            {
                'accent': 'amber',
                'icon': 'fa-wand-magic-sparkles',
                'eyebrow': 'ابزارهای هوشمند',
                'title': 'محاسبات تخصصی املاک',
                'desc': 'تبدیل ودیعه↔اجاره، متراژ و قیمت، کمیسیون معامله — نتیجه فوری بدون ذخیره داده.',
                'visual': 'tools',
                'image': 'images/help-tools-panel.png',
            },
            {
                'accent': 'cyan',
                'icon': 'fa-robot',
                'eyebrow': 'ربات استخراج',
                'title': 'جمع‌آوری خودکار از دیوار',
                'desc': 'فیلتر دقیق، فایلینگ منظم روی ویندوز و آپلود مستقیم در میزکار.',
                'visual': 'bot',
                'image': 'robot-estekhraj-amlak.png',
            },
        ],
        'platform_modules': [
            {
                'id': 'crm', 'size': 'hero', 'accent': 'violet',
                'icon': 'fa-chart-pie', 'decor_icon': 'clipboard_list', 'title': 'CRM مشاور املاک',
                'desc': 'قیف وضعیت، روند ۷ روزه، کانال ارتباط و شاخص‌های زنده',
                'stat': 'رایگان',
                'landing_url_name': 'seo_landing_real_estate_crm',
            },
            {
                'id': 'today', 'size': 'wide', 'accent': 'amber',
                'icon': 'fa-list-check', 'decor_icon': 'sticky_note', 'title': 'صف کار امروز',
                'desc': 'پیگیری‌های روزانه و یادآورها در یک نمای متمرکز',
                'stat': None,
            },
            {
                'id': 'analyze', 'size': 'tall', 'accent': 'emerald',
                'icon': 'fa-chart-line', 'decor_icon': 'sparkles', 'title': 'تحلیل چندلایه',
                'desc': 'عمق بازار، پرت‌ها، قیمت متر و گزارش سطح‌بندی‌شده',
                'stat': None,
            },
            {
                'id': 'map', 'size': 'normal', 'accent': 'sky',
                'icon': 'fa-map-location-dot', 'decor_icon': 'map_pin', 'title': 'نقشه Pro',
                'desc': 'نمای جغرافیایی با فیلتر و خوشه‌بندی',
                'stat': None,
            },
            {
                'id': 'filing', 'size': 'normal', 'accent': 'indigo',
                'icon': 'fa-database', 'decor_icon': 'layers', 'title': 'فایلینگ دیوار',
                'desc': 'آپلود، جستجو و مدیریت مجموعه‌داده',
                'stat': None,
            },
            {
                'id': 'compare', 'size': 'normal', 'accent': 'cyan',
                'icon': 'fa-scale-balanced', 'decor_icon': 'ruler', 'title': 'مقایسه دوره‌ای',
                'desc': 'تغییرات بازار بین دو استخراج',
                'stat': None,
            },
            {
                'id': 'tools', 'size': 'normal', 'accent': 'amber',
                'icon': 'fa-wand-magic-sparkles', 'decor_icon': 'sparkles', 'title': 'ابزار هوشمند',
                'desc': 'ودیعه، متراژ، کمیسیون',
                'stat': None,
            },
            {
                'id': 'automation', 'size': 'normal', 'accent': 'rose',
                'icon': 'fa-robot', 'decor_icon': 'rocket', 'title': 'اتوماسیون',
                'desc': 'قوانین خودکار پیگیری مخاطب',
                'stat': None,
            },
            {
                'id': 'templates', 'size': 'normal', 'accent': 'pink',
                'icon': 'fa-message', 'decor_icon': 'file_text', 'title': 'قالب پیام',
                'desc': 'پیام‌های آماده واتساپ',
                'stat': None,
            },
            {
                'id': 'calendar', 'size': 'normal', 'accent': 'teal',
                'icon': 'fa-calendar', 'decor_icon': 'sticky_note', 'title': 'تقویم',
                'desc': 'رویدادها و برنامه‌ریزی',
                'stat': None,
            },
            {
                'id': 'team', 'size': 'wide', 'accent': 'rose',
                'icon': 'fa-users-gear', 'decor_icon': 'share_2', 'title': 'مدیریت تیم',
                'desc': 'عملکرد اعضا، تخصیص مشتری و همگام‌سازی آژانس',
                'stat': 'رایگان',
            },
        ],
        'workflow_steps': [
            {'icon': 'fa-robot', 'decor_icon': 'rocket', 'title': 'استخراج', 'desc': 'ربات دیوار', 'accent': 'violet'},
            {'icon': 'fa-upload', 'decor_icon': 'upload', 'title': 'فایلینگ', 'desc': 'آپلود در میزکار', 'accent': 'indigo'},
            {'icon': 'fa-chart-line', 'decor_icon': 'sparkles', 'title': 'تحلیل', 'desc': 'بینش بازار', 'accent': 'emerald'},
            {'icon': 'fa-map', 'decor_icon': 'map_pin', 'title': 'نقشه', 'desc': 'نمای جغرافیایی', 'accent': 'sky'},
            {'icon': 'fa-users', 'decor_icon': 'clipboard_list', 'title': 'CRM', 'desc': 'مدیریت مشتری', 'accent': 'violet'},
            {'icon': 'fa-handshake', 'decor_icon': 'coins', 'title': 'معامله', 'desc': 'بستن قرارداد', 'accent': 'amber'},
        ],
        'crm_suite': {
            'kicker': 'مدیریت مشتری',
            'title': 'CRM که واقعاً برای مشاور ساخته شده',
            'desc': (
                'نه یک دفترچه ساده — یک سیستم کامل با قیف فروش، صف کار روزانه، '
                'یادآور هوشمند، اتوماسیون پیگیری و قالب پیام واتساپ.'
            ),
            'image': 'images/help-crm-dashboard.png',
            'features': [
                {'icon': 'fa-address-book', 'decor_icon': 'clipboard_list', 'title': 'مخاطبین و قیف', 'desc': 'وضعیت، اولویت، کانبان و تاریخ پیگیری'},
                {'icon': 'fa-handshake', 'decor_icon': 'coins', 'title': 'معاملات', 'desc': 'ردیابی پرونده از سرنخ تا قرارداد'},
                {'icon': 'fa-list-check', 'decor_icon': 'sticky_note', 'title': 'صف کار امروز', 'desc': 'تمرکز روی کارهای روز — بدون فراموشی'},
                {'icon': 'fa-robot', 'decor_icon': 'sparkles', 'title': 'اتوماسیون', 'desc': 'هشدار مخاطب راکد و قوانین خودکار'},
                {'icon': 'fa-message', 'decor_icon': 'share_2', 'title': 'قالب پیام', 'desc': 'ارسال سریع با متغیرهای شخصی‌سازی‌شده'},
                {'icon': 'fa-calendar', 'decor_icon': 'upload', 'title': 'تقویم', 'desc': 'قرارها، یادآورها و رویدادها'},
            ],
            'metrics': [
                {'label': 'وضعیت مخاطب', 'value': '۷ مرحله'},
                {'label': 'نمودار روند', 'value': '۷ / ۳۰ روز'},
                {'label': 'کانال ارتباط', 'value': '۴+ کانال'},
            ],
        },
        'capability_groups': [
            {
                'id': 'crm',
                'label': 'مدیریت مشتری',
                'desc': 'قیف فروش، پیگیری روزانه و اتوماسیون در یک جریان کاری',
                'icon': 'fa-users',
                'decor_icon': 'clipboard_list',
                'accent': 'violet',
                'pillar_link': {
                    'title': 'CRM مشاور املاک',
                    'desc': 'راهنمای کامل CRM رایگان و میزکار',
                    'landing_url_name': 'seo_landing_real_estate_crm',
                },
                'items': [
                    {'icon': 'fa-address-book', 'title': 'مخاطبین', 'desc': 'پروفایل، وضعیت، قیف و تاریخ پیگیری'},
                    {'icon': 'fa-handshake', 'title': 'معاملات', 'desc': 'ردیابی پرونده از سرنخ تا قرارداد'},
                    {'icon': 'fa-building', 'title': 'فایل‌های شخصی', 'desc': 'املاک تحت مدیریت شما با جزئیات کامل'},
                    {'icon': 'fa-list-check', 'title': 'صف کار امروز', 'desc': 'تمرکز روی پیگیری‌های روز'},
                    {'icon': 'fa-bell', 'title': 'یادآورها', 'desc': 'قرارها و کارهای زمان‌بندی‌شده'},
                    {'icon': 'fa-robot', 'title': 'اتوماسیون', 'desc': 'قوانین خودکار برای مخاطب راکد'},
                    {'icon': 'fa-message', 'title': 'قالب پیام', 'desc': 'پیام واتساپ با متغیرهای پویا'},
                    {'icon': 'fa-calendar', 'title': 'تقویم', 'desc': 'نمای زمانی رویدادها و پیگیری‌ها'},
                ],
            },
            {
                'id': 'data',
                'label': 'داده و فایلینگ',
                'desc': 'استخراج، سازماندهی و نمایش جغرافیایی آگهی‌ها',
                'icon': 'fa-database',
                'decor_icon': 'layers',
                'accent': 'sky',
                'items': [
                    {'icon': 'fa-database', 'title': 'فایلینگ دیوار', 'desc': 'آپلود و سازماندهی مجموعه‌داده‌های استخراج‌شده'},
                    {'icon': 'fa-map-location-dot', 'title': 'نقشه Pro', 'desc': 'خوشه‌بندی، فیلتر، basemap و خروجی تصویر'},
                    {'icon': 'fa-code-compare', 'title': 'مقایسه دوره‌ای', 'desc': 'تغییرات بازار بین دو استخراج'},
                ],
            },
            {
                'id': 'intel',
                'label': 'تحلیل و ابزار',
                'desc': 'تصمیم‌گیری مبتنی بر داده و محاسبات تخصصی',
                'icon': 'fa-chart-line',
                'decor_icon': 'sparkles',
                'accent': 'emerald',
                'items': [
                    {'icon': 'fa-chart-pie', 'title': 'تحلیل چندلایه', 'desc': 'سطح ۱ تا ۳ — از نگاه سریع تا عمق بازار'},
                    {'icon': 'fa-chart-area', 'title': 'روند و پرت‌ها', 'desc': 'نمودار قیمت، توزیع و شناسایی داده پرت'},
                    {'icon': 'fa-wand-magic-sparkles', 'title': 'ابزارهای هوشمند', 'desc': 'ودیعه↔اجاره، متراژ، کمیسیون — نتیجه فوری'},
                ],
            },
        ],
        'capabilities': [
            {'icon': 'fa-address-book', 'title': 'مخاطبین', 'desc': 'پروفایل، وضعیت، اولویت و تاریخ پیگیری'},
            {'icon': 'fa-building', 'title': 'فایل‌های املاک', 'desc': 'ثبت و مدیریت پرونده‌های تحت مدیریت شما'},
            {'icon': 'fa-bell', 'title': 'یادآورها', 'desc': 'پیگیری قرارها و کارهای روزانه'},
            {'icon': 'fa-database', 'title': 'فایلینگ دیوار', 'desc': 'آپلود و سازماندهی مجموعه‌داده‌های استخراج‌شده'},
            {'icon': 'fa-chart-pie', 'title': 'تحلیل آماری', 'desc': 'نمودار قیمت، توزیع و شناسایی داده پرت'},
            {'icon': 'fa-map-location-dot', 'title': 'نقشه تعاملی', 'desc': 'نمایش جغرافیایی آگهی‌ها'},
            {'icon': 'fa-code-compare', 'title': 'مقایسه دوره‌ای', 'desc': 'تغییرات بازار بین دو استخراج'},
            {'icon': 'fa-wand-magic-sparkles', 'title': 'ابزارهای هوشمند', 'desc': 'قیمت متر، تبدیل رهن و محاسبات املاک'},
        ],
        'compare': {
            'summary': {
                'good_label': 'با فایلینگ دیوار',
                'bad_label': 'روش سنتی',
                'good_score': '۴ از ۴',
            },
            'rows': [
                {
                    'good': {'icon': 'fa-bolt', 'title': 'سرعت', 'desc': 'استخراج خودکار در چند دقیقه به‌جای ساعت‌ها کار دستی'},
                    'bad': {'icon': 'fa-hourglass', 'title': 'کندی', 'desc': 'کپی دستی آگهی‌ها از دیوار'},
                    'score': 92,
                },
                {
                    'good': {'icon': 'fa-bullseye', 'title': 'دقت', 'desc': 'ثبت کامل فیلدها بدون خطای انسانی'},
                    'bad': {'icon': 'fa-eye-slash', 'title': 'از دست‌رفتن', 'desc': 'از دست رفتن آگهی‌های جدید و مهم'},
                    'score': 88,
                },
                {
                    'good': {'icon': 'fa-chart-line', 'title': 'تحلیل', 'desc': 'میانگین قیمت، نمودار و مقایسه دوره‌ای'},
                    'bad': {'icon': 'fa-file-excel', 'title': 'پراکندگی', 'desc': 'فایل‌های پراکنده بدون ساختار'},
                    'score': 90,
                },
                {
                    'good': {'icon': 'fa-clock', 'title': 'زمان‌بندی', 'desc': 'پیگیری مشتری با یادآور و CRM یکپارچه'},
                    'bad': {'icon': 'fa-question', 'title': 'حدس', 'desc': 'قیمت‌گذاری بدون داده کافی بازار'},
                    'score': 85,
                },
            ],
        },
        'data_sample': {
            'id': 'A-48291',
            'badge': 'استخراج کامل',
            'title': 'آپارتمان ۸۵ متری نوساز',
            'type': 'فروش مسکونی',
            'price_display': {
                'label': 'قیمت',
                'amount': '۴,۵۰۰,۰۰۰,۰۰۰',
                'unit': 'تومان',
            },
            'quick_facts': [
                {'icon': 'fa-ruler-combined', 'value': '۸۵ متر'},
                {'icon': 'fa-bed', 'value': '۲ خواب'},
                {'icon': 'fa-building', 'value': 'طبقه ۳'},
            ],
            'narrative': 'نوساز، پارکینگ و انباری، آسانسور',
            'amenity_tags': ['آسانسور', 'پارکینگ', 'انباری'],
            'clusters': [
                {
                    'title': 'قیمت‌گذاری',
                    'icon': 'fa-coins',
                    'decor_icon': 'coins',
                    'accent': 'amber',
                    'fields': [
                        {'label': 'ودیعه', 'value': '—'},
                        {'label': 'اجاره', 'value': '—'},
                    ],
                },
                {
                    'title': 'موقعیت',
                    'icon': 'fa-location-dot',
                    'decor_icon': 'map_pin',
                    'accent': 'sky',
                    'fields': [
                        {'label': 'شهر', 'value': 'شیراز'},
                        {'label': 'محله', 'value': 'معالی‌آباد'},
                        {'label': 'آدرس', 'value': 'بلوار دریای شمال'},
                        {'label': 'مختصات', 'value': '29.591°N · 52.518°E', 'mono': True},
                    ],
                },
                {
                    'title': 'مشخصات ملک',
                    'icon': 'fa-ruler-combined',
                    'decor_icon': 'ruler',
                    'accent': 'emerald',
                    'fields': [
                        {'label': 'متراژ', 'value': '۸۵ متر'},
                        {'label': 'اتاق', 'value': '۲ خواب'},
                        {'label': 'طبقه', 'value': '۳'},
                        {'label': 'سال ساخت', 'value': '۱۴۰۲'},
                    ],
                },
                {
                    'title': 'متادیتا',
                    'icon': 'fa-fingerprint',
                    'accent': 'violet',
                    'fields': [
                        {'label': 'آگهی‌دهنده', 'value': 'مالک'},
                        {'label': 'لینک آگهی', 'value': 'divar.ir/v/abc123', 'mono': True},
                        {'label': 'تاریخ انتشار', 'value': '۱۴۰۳/۰۹/۱۵'},
                        {'label': 'تاریخ استخراج', 'value': '۱۴۰۳/۰۹/۱۶'},
                        {'label': 'شناسه یکتا', 'value': 'A-48291', 'mono': True},
                    ],
                },
            ],
            'fields': [
                {'label': 'قیمت', 'value': '۴,۵۰۰,۰۰۰,۰۰۰ تومان'},
                {'label': 'ودیعه', 'value': '—'},
                {'label': 'اجاره', 'value': '—'},
                {'label': 'توضیحات', 'value': 'نوساز، پارکینگ و انباری، آسانسور', 'wide': True},
                {'label': 'شهر', 'value': 'شیراز'},
                {'label': 'محله', 'value': 'معالی‌آباد'},
                {'label': 'آدرس', 'value': 'بلوار دریای شمال'},
                {'label': 'مختصات', 'value': '29.591°N · 52.518°E'},
                {'label': 'متراژ', 'value': '۸۵ متر'},
                {'label': 'اتاق', 'value': '۲ خواب'},
                {'label': 'طبقه', 'value': '۳'},
                {'label': 'سال ساخت', 'value': '۱۴۰۲'},
                {'label': 'امکانات', 'value': 'آسانسور · پارکینگ · انباری', 'wide': True},
                {'label': 'آگهی‌دهنده', 'value': 'مالک'},
                {'label': 'لینک آگهی', 'value': 'divar.ir/v/abc123'},
                {'label': 'تاریخ انتشار', 'value': '۱۴۰۳/۰۹/۱۵'},
                {'label': 'تاریخ استخراج', 'value': '۱۴۰۳/۰۹/۱۶'},
                {'label': 'شناسه یکتا', 'value': 'A-48291'},
            ],
            'fields_count': '۲۴+',
            'formats': ['Excel', 'CSV'],
        },
        'transaction_types': [
            {'label': 'فروش مسکونی', 'icon': 'fa-house', 'accent': 'violet'},
            {'label': 'اجاره مسکونی', 'icon': 'fa-key', 'accent': 'sky'},
            {'label': 'فروش اداری', 'icon': 'fa-building', 'accent': 'indigo'},
            {'label': 'اجاره اداری', 'icon': 'fa-store', 'accent': 'cyan'},
            {'label': 'زمین و باغ', 'icon': 'fa-tree', 'accent': 'emerald'},
            {'label': 'پروژه ساخت‌وساز', 'icon': 'fa-hammer', 'accent': 'amber'},
            {'label': 'صنعتی', 'icon': 'fa-industry', 'accent': 'slate'},
            {'label': 'کشاورزی', 'icon': 'fa-wheat-awn', 'accent': 'lime'},
        ],
        'bot_spotlight': {
            'eyebrow': 'ربات استخراج',
            'flow': [
                {'icon': 'fa-windows', 'decor_icon': 'rocket', 'text': 'نصب روی ویندوز — استخراج خودکار'},
                {'icon': 'fa-folder', 'decor_icon': 'layers', 'text': 'فایلینگ منظم در پوشه', 'code': 'output'},
                {'icon': 'fa-layer-group', 'decor_icon': 'upload', 'text': 'آپلود و تحلیل در میزکار'},
            ],
            'guide_label': 'راهنمای نصب و فعال‌سازی',
        },
        'faq_section': {
            'eyebrow': 'پشتیبانی',
            'title': 'سوالات متداول',
            'desc': 'پاسخ سوالات رایج قبل از شروع کار با فایلینگ دیوار',
        },
        'cta_section': {
            'title': 'الان رایگان شروع کن؛ ربات استخراج را بعداً اضافه کن',
            'desc': (
                'میزکار وب برای CRM، فایل شخصی، پیگیری و تیم — بدون نصب. '
                'وقتی به استخراج و تحلیل عمیق نیاز داشتی، لایسنس ربات را فعال کن.'
            ),
            'primary_label': 'شروع رایگان',
            'secondary_label': 'مشاهده آموزش‌ها',
            'secondary_url_name': 'education',
        },
        'faqs': [
            {
                'q': 'CRM فایلینگ دیوار رایگان است؟',
                'a': 'بله — مخاطبین، معاملات، فایل‌های شخصی، صف امروز، یادآور، تقویم، '
                     'قالب پیام، اتوماسیون و مدیریت تیم در میزکار رایگان است. '
                     'فایلینگ مجموعهٔ دیوار، تحلیل چندلایه و نقشه Pro با لایسنس ربات فعال می‌شوند.',
            },
            {
                'q': 'دستیار هوشمند چه کارهایی انجام می‌دهد؟',
                'a': 'در میزکار می‌توانی با فرمان طبیعی (متن یا صدا) مخاطب جدید، فایل شخصی و یادآوری ثبت کنی. '
                     'خلاصه هوشمند هم به خواندن سریع‌تر جزئیات فایل کمک می‌کند. '
                     'هر اقدام مهم پس از تأیید تو ذخیره می‌شود.',
            },
            {
                'q': 'آیا برای استفاده از میزکار نیاز به نصب برنامه دارم؟',
                'a': 'خیر — میزکار از مرورگر در دسترس است. '
                     'ربات استخراج آگهی روی ویندوز نصب می‌شود و خروجی را می‌توانی در میزکار آپلود کنی.',
            },
            {
                'q': 'ربات استخراج روی چه دستگاهی اجرا می‌شود؟',
                'a': 'ربات روی ویندوز اجرا می‌شود و آگهی‌های دیوار را طبق فیلترهای تو استخراج می‌کند. '
                     'خروجی در پوشهٔ منظم ذخیره می‌شود و برای فایلینگ و تحلیل در میزکار آپلود می‌شود.',
            },
            {
                'q': 'چه امکاناتی در میزکار رایگان است؟',
                'a': 'CRM کامل شامل مخاطبین، معاملات، فایل‌های شخصی، یادآور، تقویم، قالب پیام و اتوماسیون '
                     'رایگان است. فایلینگ دیوار، تحلیل، نقشه و مقایسه با خرید لایسنس ربات فعال می‌شوند.',
            },
            {
                'q': 'آیا ربات در شهر من هم کار می‌کند؟',
                'a': 'بله — هر شهری که در دیوار صفحه اختصاصی و آگهی فعال دارد، '
                     'قابل استخراج است. فایلینگ به‌صورت استان / شهر / محله سازماندهی می‌شود '
                     'و محدود به یک منطقه خاص نیست.',
            },
            {
                'q': 'تحلیل بازار چه چیزهایی نشان می‌دهد؟',
                'a': 'گزارش چندلایه شامل نگاه سریع، قیمت متر، عمق بازار، پرت‌ها، روند، '
                     'اعتماد تحلیل و نمودارهای تعاملی — همه از داده‌های واقعی استخراج‌شده.',
            },
            {
                'q': 'ربات چگونه فایلینگ می‌سازد؟',
                'a': 'ربات روی ویندوز اجرا می‌شود و خروجی را در پوشه output با ساختار '
                     'استان/شهر/محله ذخیره می‌کند. هر فایل مربوط به یک نوع معامله است.',
            },
            {
                'q': 'پس از خرید چه زمانی امکانات باز می‌شود؟',
                'a': 'پس از پرداخت، کلید لایسنس در داشبورد صادر می‌شود. '
                     'در اپ اندروید با همان حساب وارد شوید، یا در ربات ویندوز کلید را فعال کنید — '
                     'سپس فایلینگ و تحلیل باز می‌شود.',
            },
            {
                'q': 'آیا داده‌ها روی سرور شما ذخیره می‌شود؟',
                'a': 'استخراج روی سیستم شما انجام می‌شود. آپلود در میزکار اختیاری است '
                     'و برای تحلیل و CRM در حساب کاربری شما نگهداری می‌شود.',
            },
        ],
    }
