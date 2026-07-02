"""محتوای مرکز آموزش عمومی — مسیر یادگیری، دوره‌ها و منابع."""

_PATH_COVERS = {
    'starter': ('help-workspace-home.png', 'میزکار — نقطه شروع روز کاری شما'),
    'bot': ('help-bot-extract-tab.png', 'استخراج آگهی‌های هدف از دیوار'),
    'pro': ('help-analyze-dashboard.png', 'تحلیل قیمت و روند محله'),
}

_MODULE_COVERS = {
    'crm-basics': ('help-crm-dashboard.png', 'داشبورد — وضعیت مشتریان و پیگیری‌ها'),
    'bot-extraction': ('help-bot-install.png', 'نصب ربات روی ویندوز'),
    'filing-upload': ('help-upload-single.png', 'آپلود فایل استخراج در فایلینگ'),
    'market-analysis': ('help-analyze-dashboard.png', 'میانگین قیمت و آمار محله'),
    'crm-advanced': ('help-crm-deals.png', 'قیف معامله — از بازدید تا قرارداد'),
    'resources': ('help-settings-modal.png', 'تنظیمات میزکار و آژانس'),
}

_MODULE_LESSON_IMAGES = {
    'crm-basics': [
        ('help-workspace-home.png', 'نمای کلی میزکار'),
        ('help-crm-contacts.png', 'پرونده مشتریان'),
        ('help-crm-today.png', 'تماس‌ها و بازدیدهای امروز'),
        ('help-crm-properties.png', 'فایل‌های ملک شما'),
    ],
    'bot-extraction': [
        ('help-bot-install.png', 'اولین اجرای ربات'),
        ('help-bot-extract-tab.png', 'انتخاب شهر و محله هدف'),
        ('help-bot-output-folder.png', 'پوشه خروجی آگهی‌ها'),
        ('help-bot-license.png', 'فعال‌سازی لایسنس'),
    ],
    'filing-upload': [
        ('help-upload-single.png', 'آپلود یک فایل'),
        ('help-upload-bulk.png', 'آپلود چند فایل یک‌جا'),
        ('help-dataset-table.png', 'مرور لیست آگهی‌ها'),
        ('help-listing-detail.png', 'جزئیات هر آگهی'),
    ],
    'market-analysis': [
        ('help-analyze-dashboard.png', 'تحلیل قیمت و روند'),
        ('help-map-view.png', 'آگهی‌ها روی نقشه'),
        ('help-compare-files.png', 'مقایسه دو منطقه یا زمان'),
        ('help-tools-panel.png', 'ابزارهای کارشناسی'),
    ],
    'crm-advanced': [
        ('help-crm-deals.png', 'پیگیری معاملات'),
        ('help-crm-calendar.png', 'تقویم بازدید و قرار'),
        ('help-crm-automation.png', 'پیام خودکار به مشتری'),
        ('help-crm-team.png', 'تیم آژانس'),
    ],
    'resources': [
        ('help-crm-templates.png', 'قالب پیام آماده'),
        ('help-bot-license.png', 'راهنمای فعال‌سازی'),
        ('help-crm-contact-detail.png', 'پرونده کامل مشتری'),
        ('help-crm-reminders.png', 'یادآور تماس'),
    ],
}

_GALLERY_ITEMS = [
    ('help-bot-install.png', 'نصب ربات — آماده‌سازی اولین استخراج', 'bot', 'violet'),
    ('help-bot-license.png', 'فعال‌سازی لایسنس روی سیستم شما', 'bot', 'violet'),
    ('help-bot-extract-tab.png', 'انتخاب محله و نوع معامله (فروش / اجاره)', 'bot', 'violet'),
    ('help-bot-output-folder.png', 'فایل‌های خروجی آماده آپلود', 'bot', 'violet'),
    ('help-workspace-home.png', 'میزکار — خلاصه وضعیت روز', 'workspace', 'emerald'),
    ('help-upload-single.png', 'آپلود فایل تکی در فایلینگ', 'filing', 'sky'),
    ('help-upload-bulk.png', 'آپلود گروهی — چند محله یک‌جا', 'filing', 'sky'),
    ('help-dataset-table.png', 'فیلتر و جستجو در آگهی‌های محله', 'filing', 'sky'),
    ('help-listing-detail.png', 'جزئیات آگهی و قیمت هر متر', 'filing', 'sky'),
    ('help-analyze-dashboard.png', 'میانگین قیمت و روند محله', 'analysis', 'amber'),
    ('help-map-view.png', 'توزیع آگهی‌ها روی نقشه', 'analysis', 'amber'),
    ('help-compare-files.png', 'مقایسه قیمت بین دو فایل', 'analysis', 'amber'),
    ('help-tools-panel.png', 'تبدیل رهن و اجاره، بنچمارک', 'analysis', 'amber'),
    ('help-crm-dashboard.png', 'خلاصه مشتریان و پیگیری‌های معوق', 'crm', 'rose'),
    ('help-crm-today.png', 'لیست تماس و بازدید امروز', 'crm', 'rose'),
    ('help-crm-contacts.png', 'پرونده مشتریان و سرنخ‌ها', 'crm', 'rose'),
    ('help-crm-contact-detail.png', 'تاریخچه تماس و تطبیق ملک', 'crm', 'rose'),
    ('help-crm-properties.png', 'فایل‌های ملک آژانس', 'crm', 'rose'),
    ('help-crm-deals.png', 'مراحل معامله تا عقد قرارداد', 'crm', 'rose'),
    ('help-crm-calendar.png', 'برنامه بازدید و جلسات', 'crm', 'rose'),
    ('help-crm-reminders.png', 'یادآور تماس با خریدار یا مالک', 'crm', 'rose'),
    ('help-crm-templates.png', 'پیام آماده برای واتساپ و تماس', 'crm', 'rose'),
    ('help-crm-automation.png', 'پیگیری خودکار مشتریان', 'crm', 'rose'),
    ('help-crm-team.png', 'تقسیم مشتری بین مشاوران', 'crm', 'rose'),
    ('help-settings-modal.png', 'تنظیمات تم و آژانس', 'workspace', 'emerald'),
]


def _enrich_education_content(content):
    for path in content['paths']:
        cover = _PATH_COVERS.get(path['id'])
        if cover:
            path['cover_image'], path['cover_caption'] = cover

    for mod in content['modules']:
        cover = _MODULE_COVERS.get(mod['id'])
        if cover:
            mod['cover_image'], mod['cover_caption'] = cover
        images = _MODULE_LESSON_IMAGES.get(mod['id'], [])
        for lesson, img in zip(mod['lessons'], images):
            lesson['image'], lesson['image_caption'] = img

    content['featured'][0]['image'] = 'help-bot-license.png'
    content['featured'][0]['image_caption'] = 'فعال‌سازی ربات — گام‌به‌گام'
    content['featured'][1]['image'] = 'help-crm-dashboard.png'
    content['featured'][1]['image_caption'] = 'راهنمای کامل میزکار مشاور'

    content['hero_visual'] = [
        {'image': 'help-crm-contacts.png', 'caption': 'پرونده مشتری', 'accent': 'emerald'},
        {'image': 'help-analyze-dashboard.png', 'caption': 'تحلیل محله', 'accent': 'amber'},
        {'image': 'help-map-view.png', 'caption': 'نقشه آگهی', 'accent': 'sky'},
        {'image': 'help-crm-deals.png', 'caption': 'پیگیری معامله', 'accent': 'rose'},
    ]

    content['gallery'] = {
        'title': 'تصاویر واقعی از میزکار',
        'subtitle': 'هر اسکرین‌شات دقیقاً همان چیزی است که در کار روزانه می‌بینید — کلیک کنید تا بزرگ شود',
        'categories': [
            {'id': 'all', 'label': 'همه', 'icon': 'fa-grid-2'},
            {'id': 'crm', 'label': 'مشتری و معامله', 'icon': 'fa-handshake'},
            {'id': 'bot', 'label': 'استخراج دیوار', 'icon': 'fa-robot'},
            {'id': 'filing', 'label': 'فایلینگ', 'icon': 'fa-folder-open'},
            {'id': 'analysis', 'label': 'تحلیل بازار', 'icon': 'fa-chart-line'},
            {'id': 'workspace', 'label': 'میزکار', 'icon': 'fa-layer-group'},
        ],
        'items': [
            {
                'image': img,
                'caption': caption,
                'category': cat,
                'accent': accent,
            }
            for img, caption, cat, accent in _GALLERY_ITEMS
        ],
    }
    return content


def education_hub_content():
    content = {
        'hero': {
            'eyebrow': 'آموزش مشاوران املاک',
            'title': 'از ثبت مشتری تا تحلیل محله — همه‌چیز در یک جا',
            'lead': (
                'میزکار فایلینگ دیوار برای مشاورانی ساخته شده که هر روز با خریدار، مالک و آگهی سر و کار دارند. '
                'اینجا یاد می‌گیرید چطور مشتری ثبت کنید، آگهی‌های محله را جمع کنید، قیمت را تحلیل کنید '
                'و معامله را تا قرارداد پیگیری کنید — با تصویر واقعی از هر بخش.'
            ),
        },
        'stats': [
            {'num': 'رایگان', 'label': 'مدیریت مشتری و ملک'},
            {'num': '۲۵+', 'label': 'آموزش تصویری'},
            {'num': '۳', 'label': 'مسیر بر اساس تجربه شما'},
            {'num': '۶', 'label': 'بخش تخصصی'},
        ],
        'sections': {
            'paths': {'title': 'از کجا شروع کنم؟', 'subtitle': 'مسیر مناسب سطح کار شما — هر کدام با تصویر و لینک مستقیم'},
            'modules': {'title': 'آموزش بخش‌به‌بخش', 'subtitle': 'هر ماژول با اسکرین‌شات واقعی — دقیقاً همان صفحه‌ای که در میزکار می‌بینید'},
            'gallery': {'title': 'گالری تصاویر', 'subtitle': 'مرور سریع همه بخش‌ها قبل از شروع کار'},
            'featured': {'title': 'دو راهنمای ضروری', 'subtitle': 'بیشتر مشاوران از همین‌جا شروع می‌کنند'},
            'faq': {'title': 'سؤالات رایج مشاوران', 'subtitle': None},
            'cta': {'title': 'همین امروز شروع کنید', 'subtitle': 'ثبت‌نام رایگان — مدیریت مشتری بدون محدودیت. برای تحلیل بازار، ربات استخراج نیاز است.'},
        },
        'paths': [
            {
                'id': 'starter',
                'icon': 'fa-seedling',
                'decor_icon': 'layers',
                'accent': 'emerald',
                'badge': 'رایگان',
                'title': 'تازه‌کار',
                'subtitle': 'مدیریت مشتری — بدون نیاز به ربات',
                'desc': 'اگر تازه شروع کرده‌اید یا فعلاً فقط می‌خواهید مشتری و فایل ملک را منظم نگه دارید، از اینجا شروع کنید. رایگان و بدون محدودیت.',
                'steps': [
                    {
                        'num': '۱',
                        'title': 'ثبت‌نام و ورود',
                        'desc': 'حساب بسازید و مستقیم وارد میزکار شوید — نیازی به نصب نرم‌افزار نیست.',
                        'url_name': 'register',
                        'icon': 'fa-user-plus',
                    },
                    {
                        'num': '۲',
                        'title': 'ثبت مشتری (خریدار / مالک)',
                        'desc': 'نام، موبایل، بودجه و نوع ملک مورد نظر را ثبت کنید تا در پیگیری‌ها گم نشود.',
                        'url_name': 'workspace:crm_contacts',
                        'requires_auth': True,
                        'icon': 'fa-address-book',
                    },
                    {
                        'num': '۳',
                        'title': 'فایل ملک آژانس',
                        'desc': 'ملک‌های خودتان را — حتی بدون آگهی دیوار — در پرونده جداگانه نگه دارید.',
                        'url_name': 'workspace:crm_properties',
                        'requires_auth': True,
                        'icon': 'fa-building',
                    },
                    {
                        'num': '۴',
                        'title': 'پیگیری تماس و بازدید',
                        'desc': 'برای هر مشتری زمان تماس بعدی بگذارید؛ لیست امروز را صبح یک‌جا ببینید.',
                        'url_name': 'workspace:crm_today',
                        'requires_auth': True,
                        'icon': 'fa-bell',
                    },
                ],
            },
            {
                'id': 'bot',
                'icon': 'fa-robot',
                'decor_icon': 'rocket',
                'accent': 'violet',
                'badge': 'ربات',
                'title': 'استخراج از دیوار',
                'subtitle': 'جمع‌آوری آگهی محله هدف',
                'desc': 'برای کارشناسی قیمت و پیدا کردن ملک مناسب مشتری، باید آگهی‌های محله را منظم داشته باشید. ربات این کار را خودکار انجام می‌دهد.',
                'steps': [
                    {
                        'num': '۱',
                        'title': 'خرید لایسنس ربات',
                        'desc': 'پلن مناسب را انتخاب کنید؛ کلید لایسنس در حساب کاربری شما قرار می‌گیرد.',
                        'url_name': 'product_list',
                        'icon': 'fa-cart-shopping',
                    },
                    {
                        'num': '۲',
                        'title': 'نصب روی ویندوز',
                        'desc': 'ربات روی کامپیوتر شما اجرا می‌شود — اینترنت خانگی یا اداری کافی است.',
                        'url_name': 'license_guide',
                        'icon': 'fa-download',
                        'decor_icon': 'download',
                    },
                    {
                        'num': '۳',
                        'title': 'فعال‌سازی و اولین استخراج',
                        'desc': 'کلید را وارد کنید، شهر و محله را انتخاب کنید و استخراج را شروع کنید.',
                        'url_name': 'license_guide',
                        'anchor': 'steps',
                        'icon': 'fa-key',
                        'decor_icon': 'rocket',
                    },
                    {
                        'num': '۴',
                        'title': 'آپلود در فایلینگ میزکار',
                        'desc': 'فایل اکسل خروجی را در میزکار بارگذاری کنید تا تحلیل و نقشه فعال شود.',
                        'url_name': 'workspace:dataset_list',
                        'requires_auth': True,
                        'requires_bot': True,
                        'icon': 'fa-cloud-arrow-up',
                        'decor_icon': 'upload',
                    },
                ],
            },
            {
                'id': 'pro',
                'icon': 'fa-chart-line',
                'decor_icon': 'sparkles',
                'accent': 'sky',
                'badge': 'پیشرفته',
                'title': 'مشاور فعال',
                'subtitle': 'تحلیل بازار + پیگیری معامله',
                'desc': 'وقتی هم مشتری دارید و هم فایل آگهی محله، وقت تحلیل قیمت، پیشنهاد ملک به خریدار و بستن قرارداد است.',
                'steps': [
                    {
                        'num': '۱',
                        'title': 'تحلیل قیمت محله',
                        'desc': 'میانگین قیمت هر متر، روند هفتگی و پراکندگی را برای مذاکره با مالک ببینید.',
                        'url_name': 'workspace:dataset_list',
                        'requires_auth': True,
                        'requires_bot': True,
                        'icon': 'fa-chart-area',
                    },
                    {
                        'num': '۲',
                        'title': 'نقشه و مقایسه مناطق',
                        'desc': 'آگهی‌ها را روی نقشه ببینید یا دو محله / دو زمان را کنار هم مقایسه کنید.',
                        'url_name': 'workspace:tools',
                        'requires_auth': True,
                        'requires_bot': True,
                        'icon': 'fa-map',
                    },
                    {
                        'num': '۳',
                        'title': 'پیگیری معامله تا قرارداد',
                        'desc': 'از بازدید اول تا مذاکره و عقد — هر مرحله را در قیف معاملات ثبت کنید.',
                        'url_name': 'workspace:crm_deals',
                        'requires_auth': True,
                        'icon': 'fa-handshake',
                    },
                    {
                        'num': '۴',
                        'title': 'تیم آژانس و پیام خودکار',
                        'desc': 'مشتری را بین مشاوران تقسیم کنید و پیام پیگیری را خودکار بفرستید.',
                        'url_name': 'workspace:crm_team',
                        'requires_auth': True,
                        'icon': 'fa-users-gear',
                    },
                ],
            },
        ],
        'modules': [
            {
                'id': 'crm-basics',
                'icon': 'fa-gift',
                'accent': 'emerald',
                'badge': 'رایگان',
                'title': 'مدیریت مشتری',
                'desc': 'ثبت خریدار و مالک، پیگیری تماس و نگهداری فایل ملک — کاملاً رایگان.',
                'lessons': [
                    {
                        'title': 'ورود به میزکار',
                        'desc': 'آشنایی با داشبورد: چه کسی امروز باید تماس بگیرد و چه معامله‌ای معوق است.',
                        'duration': '۳ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-door-open',
                        'url_name': 'register',
                    },
                    {
                        'title': 'ثبت مشتری جدید',
                        'desc': 'بودجه، محله مدنظر، نوع معامله (خرید، رهن، اجاره) و یادداشت اولیه.',
                        'duration': '۵ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-user-tag',
                        'url_name': 'workspace:crm_contacts',
                        'requires_auth': True,
                    },
                    {
                        'title': 'لیست کار امروز',
                        'desc': 'تماس‌های امروز و پیگیری‌های عقب‌افتاده — اول صبح همین را باز کنید.',
                        'duration': '۴ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-list-check',
                        'url_name': 'workspace:crm_today',
                        'requires_auth': True,
                    },
                    {
                        'title': 'فایل ملک آژانس',
                        'desc': 'ملک‌های فعال، رهن کامل، اجاره و فروش — جدا از آگهی‌های دیوار.',
                        'duration': '۶ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-house-chimney',
                        'url_name': 'workspace:crm_properties',
                        'requires_auth': True,
                    },
                ],
            },
            {
                'id': 'bot-extraction',
                'icon': 'fa-robot',
                'accent': 'violet',
                'badge': 'ربات',
                'title': 'ربات استخراج دیوار',
                'desc': 'جمع‌آوری خودکار آگهی‌های محله — خروجی اکسل آماده تحلیل.',
                'lessons': [
                    {
                        'title': 'راه‌اندازی از صفر',
                        'desc': 'از خرید لایسنس تا اولین فایل اکسل — با تصویر هر مرحله.',
                        'duration': '۱۰ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-book-open',
                        'url_name': 'license_guide',
                    },
                    {
                        'title': 'انتخاب محله هدف',
                        'desc': 'کدام محله را استخراج کنید تا فایل سبک و مرتبط با مشتریانتان باشد.',
                        'duration': '۵ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-location-dot',
                        'url_name': 'license_guide',
                        'requires_bot': True,
                    },
                    {
                        'title': 'ساختار پوشه خروجی',
                        'desc': 'فایل‌ها کجا ذخیره می‌شوند و چطور برای آپلود آماده کنید.',
                        'duration': '۴ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-folder',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'bot-extraction',
                    },
                    {
                        'title': 'به‌روزرسانی آگهی‌ها',
                        'desc': 'هر چند وقت یک‌بار دوباره استخراج کنید تا قیمت‌ها به‌روز بماند.',
                        'duration': '۳ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-arrows-rotate',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'bot-extraction',
                    },
                ],
            },
            {
                'id': 'filing-upload',
                'icon': 'fa-cloud-arrow-up',
                'accent': 'sky',
                'badge': 'ربات',
                'title': 'فایلینگ آگهی‌ها',
                'desc': 'آپلود فایل استخراج، مرور آگهی‌ها و پیدا کردن ملک مناسب مشتری.',
                'lessons': [
                    {
                        'title': 'آپلود یک فایل',
                        'desc': 'یک محله را آپلود کنید و بلافاصله جدول آگهی‌ها را ببینید.',
                        'duration': '۴ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-file-arrow-up',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'workspace-filing',
                    },
                    {
                        'title': 'آپلود چند محله',
                        'desc': 'کل پوشه خروجی ربات را یک‌جا بارگذاری کنید — برای شروع سریع عالی است.',
                        'duration': '۵ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-layer-group',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'workspace-filing',
                    },
                    {
                        'title': 'جستجو در آگهی‌ها',
                        'desc': 'فیلتر بر اساس قیمت، متراژ، محله و مالک — ملک مناسب مشتری را سریع پیدا کنید.',
                        'duration': '۶ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-table',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'workspace-filing',
                    },
                    {
                        'title': 'بررسی جزئیات آگهی',
                        'desc': 'قیمت هر متر، امکانات، شماره مالک و مقایسه با میانگین محله.',
                        'duration': '۵ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-magnifying-glass-chart',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'market-analysis',
                    },
                ],
            },
            {
                'id': 'market-analysis',
                'icon': 'fa-chart-line',
                'accent': 'amber',
                'badge': 'ربات',
                'title': 'تحلیل و کارشناسی',
                'desc': 'قیمت‌گذاری ملک، مقایسه محله‌ها و پیدا کردن فرصت خرید.',
                'lessons': [
                    {
                        'title': 'میانگین قیمت محله',
                        'desc': 'قبل از مذاکره با مالک، بدانید قیمت بازار چقدر است.',
                        'duration': '۸ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-gauge-high',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'market-analysis',
                    },
                    {
                        'title': 'نقشه توزیع آگهی',
                        'desc': 'ببینید کدام خیابان‌ها بیشترین آگهی یا بهترین قیمت را دارند.',
                        'duration': '۶ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-map-location-dot',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'market-analysis',
                    },
                    {
                        'title': 'مقایسه دو فایل',
                        'desc': 'قیمت امروز را با ماه قبل مقایسه کنید — بفهمید بازار صعودی است یا نزولی.',
                        'duration': '۵ دقیقه',
                        'level': 'پیشرفته',
                        'icon': 'fa-code-compare',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'market-analysis',
                    },
                    {
                        'title': 'ابزار کارشناسی',
                        'desc': 'تبدیل رهن و اجاره، بنچمارک قیمت و فیلترهای پیشرفته.',
                        'duration': '۷ دقیقه',
                        'level': 'پیشرفته',
                        'icon': 'fa-wand-magic-sparkles',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'requires_bot': True,
                        'anchor': 'smart-tools',
                    },
                ],
            },
            {
                'id': 'crm-advanced',
                'icon': 'fa-handshake',
                'accent': 'rose',
                'badge': 'CRM',
                'title': 'معامله و تیم',
                'desc': 'از بازدید تا قرارداد — پیگیری حرفه‌ای برای مشاور و آژانس.',
                'lessons': [
                    {
                        'title': 'قیف معاملات',
                        'desc': 'هر معامله در چه مرحله‌ای است: بازدید، مذاکره، قرارداد.',
                        'duration': '۸ دقیقه',
                        'level': 'متوسط',
                        'icon': 'fa-filter',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'anchor': 'crm-deals',
                    },
                    {
                        'title': 'تقویم بازدید',
                        'desc': 'برنامه بازدید ملک‌ها را با تقویم هماهنگ کنید.',
                        'duration': '۵ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-calendar-days',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'anchor': 'crm-scheduling',
                    },
                    {
                        'title': 'پیام آماده و اتوماسیون',
                        'desc': 'متن پیگیری واتساپ را یک‌بار بنویسید، هر بار سریع بفرستید.',
                        'duration': '۷ دقیقه',
                        'level': 'پیشرفته',
                        'icon': 'fa-message',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'anchor': 'crm-communication',
                    },
                    {
                        'title': 'مدیریت تیم آژانس',
                        'desc': 'تقسیم مشتری بین مشاوران و پیگیری عملکرد هر نفر.',
                        'duration': '۱۰ دقیقه',
                        'level': 'پیشرفته',
                        'icon': 'fa-users',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                        'anchor': 'crm-team',
                    },
                ],
            },
            {
                'id': 'resources',
                'icon': 'fa-compass',
                'accent': 'violet',
                'badge': 'منابع',
                'title': 'راهنما و پشتیبانی',
                'desc': 'منابع تکمیلی برای وقتی سؤال دارید یا می‌خواهید عمیق‌تر یاد بگیرید.',
                'lessons': [
                    {
                        'title': 'مقالات تخصصی',
                        'desc': 'آخرین مطالب و نکات کاربردی در بلاگ.',
                        'duration': '—',
                        'level': 'همه',
                        'icon': 'fa-newspaper',
                        'url_name': 'blog:post_list',
                    },
                    {
                        'title': 'راهنمای نصب ربات',
                        'desc': 'ویدیوی آموزشی + مراحل فعال‌سازی — همیشه در دسترس.',
                        'duration': '۱۰ دقیقه',
                        'level': 'مقدماتی',
                        'icon': 'fa-book',
                        'url_name': 'license_guide',
                    },
                    {
                        'title': 'راهنمای کامل میزکار',
                        'desc': 'آموزش تصویری تمام بخش‌های میزکار.',
                        'duration': '۳۰+ دقیقه',
                        'level': 'همه',
                        'icon': 'fa-graduation-cap',
                        'url_name': 'workspace:help',
                        'requires_auth': True,
                    },
                    {
                        'title': 'تماس با پشتیبانی',
                        'desc': 'سؤال دارید؟ تیم ما پاسخگوست.',
                        'duration': '—',
                        'level': 'همه',
                        'icon': 'fa-headset',
                        'url_name': 'contact',
                    },
                ],
            },
        ],
        'featured': [
            {
                'icon': 'fa-book-open',
                'accent': 'emerald',
                'title': 'راهنمای فعال‌سازی ربات',
                'desc': 'ویدیوی نصب گام‌به‌گام + راهنمای متنی از خرید تا اولین فایل اکسل در میزکار.',
                'duration': '۱۰ دقیقه',
                'url_name': 'license_guide',
                'cta': 'مشاهده راهنما',
            },
            {
                'icon': 'fa-graduation-cap',
                'accent': 'violet',
                'title': 'راهنمای کامل میزکار',
                'desc': 'هر صفحه میزکار با تصویر و توضیح — از ثبت مشتری تا تحلیل محله و پیگیری معامله.',
                'duration': '۳۰+ دقیقه',
                'url_name': 'workspace:help',
                'requires_auth': True,
                'cta': 'ورود به راهنما',
                'cta_guest': 'ثبت‌نام رایگان',
                'guest_url_name': 'register',
            },
        ],
        'faq': [
            {
                'q': 'بدون خرید ربات می‌توانم مشتری ثبت کنم؟',
                'a': 'بله. ثبت مشتری، فایل ملک، یادآور تماس و پیگیری معامله کاملاً رایگان است. '
                     'ربات فقط برای جمع‌آوری آگهی دیوار و تحلیل قیمت محله لازم است.',
            },
            {
                'q': 'ربات روی مک یا موبایل هم کار می‌کند؟',
                'a': 'ربات استخراج فقط روی ویندوز اجرا می‌شود. اما میزکار از مرورگر — روی موبایل و تبلت هم — '
                     'در دسترس است و همان‌جا مشتری و معامله را مدیریت می‌کنید.',
            },
            {
                'q': 'چند وقت یک‌بار باید آگهی‌ها را به‌روز کنم؟',
                'a': 'برای محله‌های پرتحرک، هفته‌ای یک‌بار استخراج مجدد کافی است. '
                     'فایل جدید را آپلود کنید و با مقایسه، تغییر قیمت را ببینید.',
            },
            {
                'q': 'تفاوت این صفحه با راهنمای میزکار چیست؟',
                'a': 'این صفحه مسیر یادگیری و شروع سریع است. راهنمای میزکار جزئیات هر دکمه و صفحه را '
                     'با تصویر کامل توضیح می‌دهد — وقتی داخل میزکار سؤال دارید به آنجا بروید.',
            },
            {
                'q': 'اگر گیر کردم چه کار کنم؟',
                'a': 'اول راهنمای فعال‌سازی ربات را ببینید. اگر مشکل حل نشد، از صفحه تماس پیام بدهید — '
                     'معمولاً همان روز پاسخ می‌دهیم.',
            },
        ],
    }
    return _enrich_education_content(content)
