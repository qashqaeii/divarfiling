"""محتوای راهنمای جامع میزکار — آموزش ربات، CRM، تحلیل و ابزارها."""


def workspace_help_content():
    return {
        'hero': {
            'eyebrow': 'مرکز آموزش و راهنما',
            'title': 'راهنمای کامل میزکار فایلینگ دیوار',
            'lead': (
                'از نصب ربات استخراج تا CRM، تحلیل بازار و ابزارهای هوشمند — '
                'هر بخش را گام‌به‌گام یاد بگیرید و حرفه‌ای‌تر کار کنید.'
            ),
        },
        'toc': [
            {'id': 'start', 'title': 'شروع سریع', 'icon': 'fa-rocket'},
            {'id': 'bot-extraction', 'title': 'ربات استخراج', 'icon': 'fa-robot'},
            {'id': 'workspace-filing', 'title': 'فایلینگ و آپلود', 'icon': 'fa-cloud-arrow-up'},
            {'id': 'market-analysis', 'title': 'تحلیل بازار', 'icon': 'fa-chart-line'},
            {'id': 'smart-tools', 'title': 'ابزارهای هوشمند', 'icon': 'fa-wand-magic-sparkles'},
            {'id': 'crm-overview', 'title': 'داشبورد CRM', 'icon': 'fa-gauge-high'},
            {'id': 'crm-contacts', 'title': 'مخاطبین', 'icon': 'fa-address-book'},
            {'id': 'crm-properties', 'title': 'املاک شخصی', 'icon': 'fa-building'},
            {'id': 'crm-deals', 'title': 'معاملات', 'icon': 'fa-handshake'},
            {'id': 'crm-scheduling', 'title': 'تقویم و یادآور', 'icon': 'fa-calendar-days'},
            {'id': 'crm-communication', 'title': 'پیام و اتوماسیون', 'icon': 'fa-message'},
            {'id': 'crm-team', 'title': 'تیم آژانس', 'icon': 'fa-users'},
            {'id': 'workspace-settings', 'title': 'تنظیمات', 'icon': 'fa-sliders'},
            {'id': 'faq', 'title': 'سؤالات متداول', 'icon': 'fa-circle-question'},
        ],
        'quick_start': [
            {
                'num': '۱',
                'icon': 'fa-user-plus',
                'accent': 'emerald',
                'title': 'مشتری ثبت کنید',
                'desc': 'CRM رایگان — مخاطب و ملک بدون محدودیت.',
                'url_name': 'workspace:crm_contacts',
                'url_query': 'open=drawer-contact',
            },
            {
                'num': '۲',
                'icon': 'fa-cloud-arrow-up',
                'accent': 'violet',
                'title': 'فایل دیوار آپلود کنید',
                'desc': 'خروجی ربات را در فایلینگ بارگذاری کنید.',
                'url_name': 'workspace:dataset_list',
                'requires_bot': True,
                'feature': 'upload',
            },
            {
                'num': '۳',
                'icon': 'fa-chart-line',
                'accent': 'sky',
                'title': 'بازار را تحلیل کنید',
                'desc': 'قیمت، نمودار، نقشه و مقایسه محله.',
                'url_name': 'workspace:dataset_list',
                'requires_bot': True,
                'feature': 'analyze',
            },
        ],
        'daily_workflow': {
            'title': 'روال پیشنهادی هر روز',
            'subtitle': 'پنج دقیقه صبح — بقیه روز با خیال راحت',
            'steps': [
                {
                    'icon': 'fa-sun',
                    'accent': 'amber',
                    'title': 'صبح',
                    'desc': 'صف کار امروز و پیگیری‌های معوق را چک کنید.',
                    'url_name': 'workspace:crm_today',
                },
                {
                    'icon': 'fa-phone',
                    'accent': 'emerald',
                    'title': 'تماس',
                    'desc': 'بعد از هر تماس، یادداشت و یادآور بعدی را ثبت کنید.',
                    'url_name': 'workspace:crm_contacts',
                },
                {
                    'icon': 'fa-building',
                    'accent': 'violet',
                    'title': 'ملک',
                    'desc': 'فایل‌های جدید را به مشتری مناسب وصل کنید.',
                    'url_name': 'workspace:crm_properties',
                },
                {
                    'icon': 'fa-moon',
                    'accent': 'sky',
                    'title': 'شب',
                    'desc': 'یادآور فردا را بگذارید تا چیزی جا نماند.',
                    'url_name': 'workspace:crm_reminders',
                },
            ],
        },
        'guides': [
            {
                'id': 'bot-extraction',
                'icon': 'fa-robot',
                'accent': 'violet',
                'badge': 'bot',
                'title': 'آموزش ربات استخراج دیوار',
                'subtitle': 'نصب، فعال‌سازی لایسنس، استخراج آگهی و مدیریت خروجی',
                'intro': (
                    'ربات روی ویندوز شما اجرا می‌شود و آگهی‌های دیوار را به‌صورت خودکار '
                    'جمع‌آوری می‌کند. خروجی در پوشه‌ای منظم ذخیره می‌شود و سپس در میزکار آپلود می‌گردد.'
                ),
                'topics': [
                    {
                        'title': 'نصب و اولین اجرا',
                        'icon': 'fa-download',
                        'steps': [
                            {
                                'title': 'دانلود نرم‌افزار',
                                'desc': 'پس از خرید، فایل نصب ربات را از حساب کاربری یا لینک دریافتی دانلود کنید.',
                            },
                            {
                                'title': 'نصب روی ویندوز',
                                'desc': 'فایل نصب را اجرا کنید. مسیر پیش‌فرض را حفظ کنید یا پوشه دلخواه انتخاب کنید.',
                            },
                            {
                                'title': 'اجرای برنامه',
                                'desc': 'از منوی استارت، «ربات فایلینگ دیوار» را باز کنید. در اولین اجرا به تب لایسنس بروید.',
                            },
                        ],
                        'tips': [
                            'آنتی‌ویروس را برای پوشه نصب در لیست استثنا قرار دهید تا سرعت استخراج کاهش نیابد.',
                            'برای به‌روزرسانی، نسخه جدید را روی نسخه قبلی نصب کنید — داده‌ها حفظ می‌شوند.',
                        ],
                        'image': 'help-bot-install.png',
                        'image_caption': 'صفحه اول اجرای ربات — تب‌های استخراج، خروجی و لایسنس',
                        'url_name': 'license_guide',
                    },
                    {
                        'title': 'فعال‌سازی لایسنس',
                        'icon': 'fa-key',
                        'steps': [
                            {
                                'title': 'دریافت کلید',
                                'desc': 'بعد از خرید، کلید لایسنس در «حساب کاربری → داشبورد» نمایش داده می‌شود.',
                            },
                            {
                                'title': 'وارد کردن کلید',
                                'desc': 'در تب «لایسنس» ربات، کلید را paste کنید و دکمه فعال‌سازی را بزنید.',
                            },
                            {
                                'title': 'تأیید سخت‌افزار',
                                'desc': 'لایسنس به یک دستگاه متصل است. در صورت تعویض سیستم، از پشتیبانی راهنمایی بگیرید.',
                            },
                        ],
                        'tips': [
                            'تا قبل از فعال‌سازی، CRM میزکار برای شما باز است — فقط بخش تحلیل قفل می‌ماند.',
                            'کلید را با کسی به اشتراک نگذارید؛ هر کلید محدود به تعداد فعال‌سازی مشخص است.',
                        ],
                        'image': 'help-bot-license.png',
                        'image_caption': 'تب لایسنس — وارد کردن کلید و نمایش وضعیت فعال',
                        'url_name': 'license_guide',
                    },
                    {
                        'title': 'تنظیم و شروع استخراج',
                        'icon': 'fa-play',
                        'steps': [
                            {
                                'title': 'انتخاب شهر و محله',
                                'desc': 'استان، شهر و در صورت نیاز محله را از فیلترها انتخاب کنید.',
                            },
                            {
                                'title': 'نوع معامله',
                                'desc': 'فروش، رهن و اجاره یا پیش‌فروش — مطابق نیاز فایلینگ خود تنظیم کنید.',
                            },
                            {
                                'title': 'شروع استخراج',
                                'desc': 'دکمه شروع را بزنید. پیشرفت به‌صورت زنده نمایش داده می‌شود.',
                            },
                            {
                                'title': 'ادامه نیمه‌کاره',
                                'desc': 'اگر استخراج قطع شد، گزینه «ادامه از آخرین نقطه» را بزنید — از ابتدا شروع نمی‌کند.',
                            },
                        ],
                        'tips': [
                            'برای محله‌های پرتعداد، استخراج را در ساعات کم‌ترافیک اینترنت انجام دهید.',
                            'فیلتر دقیق‌تر = فایل سبک‌تر و تحلیل سریع‌تر در میزکار.',
                        ],
                        'image': 'help-bot-extract-tab.png',
                        'image_caption': 'تب استخراج — انتخاب شهر، محله و نوع معامله',
                        'requires_bot': True,
                        'feature': 'datasets',
                    },
                    {
                        'title': 'خروجی و ساختار پوشه‌ها',
                        'icon': 'fa-folder-tree',
                        'steps': [
                            {
                                'title': 'پوشه output',
                                'desc': 'فایل‌ها در پوشه output با ساختار استان/شهر/محله ذخیره می‌شوند.',
                            },
                            {
                                'title': 'فرمت فایل',
                                'desc': 'Excel (پیش‌فرض)، CSV یا JSON — در تنظیمات خروجی قابل تغییر است.',
                            },
                            {
                                'title': 'تصاویر آگهی',
                                'desc': 'در صورت فعال بودن، تصاویر در زیرپوشه‌های مرتبط ذخیره می‌شوند.',
                            },
                            {
                                'title': 'استخراج مجدد',
                                'desc': 'اجرای دوباره روی همان محله، فایل را merge می‌کند — داده تکراری اضافه نمی‌شود.',
                            },
                        ],
                        'tips': [
                            'هر هفته یک بار استخراج تازه بگیرید و در میزکار با فایل قبلی مقایسه کنید.',
                            'نام پوشه‌ها را دستی تغییر ندهید — آپلود bulk به ساختار وابسته است.',
                        ],
                        'image': 'help-bot-output-folder.png',
                        'image_caption': 'تب خروجی — مسیر پوشه output و لیست فایل‌های ساخته‌شده',
                        'requires_bot': True,
                        'feature': 'datasets',
                    },
                ],
            },
            {
                'id': 'workspace-filing',
                'icon': 'fa-cloud-arrow-up',
                'accent': 'sky',
                'badge': 'bot',
                'title': 'فایلینگ دیوار و آپلود',
                'subtitle': 'بارگذاری فایل، مدیریت مجموعه‌ها و جدول آگهی‌ها',
                'intro': (
                    'پس از استخراج، خروجی ربات را در میزکار آپلود کنید. '
                    'می‌توانید یک فایل تکی یا کل پوشه output را یک‌جا بارگذاری کنید.'
                ),
                'topics': [
                    {
                        'title': 'نمای کلی و آپلود سریع',
                        'icon': 'fa-house',
                        'steps': [
                            {
                                'title': 'دکمه آپلود',
                                'desc': 'از نمای کلی میزکار، دکمه «آپلود» در بالای صفحه را بزنید.',
                            },
                            {
                                'title': 'انتخاب فایل',
                                'desc': 'فایل Excel، CSV یا JSON خروجی ربات را انتخاب کنید.',
                            },
                            {
                                'title': 'نام مجموعه',
                                'desc': 'یک نام توصیفی بگذارید — مثلاً «تهران-جردن-فروش-۱۴۰۴/۰۳».',
                            },
                        ],
                        'tips': ['نام‌گذاری منظم کمک می‌کند هنگام مقایسه فایل‌ها گیج نشوید.'],
                        'image': 'help-workspace-home.png',
                        'image_caption': 'نمای کلی میزکار — دکمه‌های آپلود، مخاطب و میانبرها',
                        'url_name': 'workspace:home',
                    },
                    {
                        'title': 'آپلود تکی',
                        'icon': 'fa-file-arrow-up',
                        'steps': [
                            {
                                'title': 'رفتن به فایلینگ',
                                'desc': 'منوی کناری → «فایلینگ دیوار» → دکمه «آپلود فایل».',
                            },
                            {
                                'title': 'بررسی پیش‌نمایش',
                                'desc': 'تعداد ردیف و ستون‌های شناسایی‌شده را قبل از تأیید ببینید.',
                            },
                            {
                                'title': 'تأیید و پردازش',
                                'desc': 'پس از پردازش، به جدول آگهی‌ها هدایت می‌شوید.',
                            },
                        ],
                        'image': 'help-upload-single.png',
                        'image_caption': 'مودال آپلود تکی — انتخاب فایل و نام مجموعه',
                        'url_name': 'workspace:dataset_upload',
                        'requires_bot': True,
                        'feature': 'upload',
                    },
                    {
                        'title': 'آپلود پوشه (Bulk)',
                        'icon': 'fa-folder-open',
                        'steps': [
                            {
                                'title': 'آپلود bulk',
                                'desc': 'از صفحه فایلینگ، «آپلود پوشه» را انتخاب کنید.',
                            },
                            {
                                'title': 'انتخاب پوشه output',
                                'desc': 'کل پوشه خروجی ربات را انتخاب کنید — همه زیرپوشه‌ها پردازش می‌شوند.',
                            },
                            {
                                'title': 'پیشرفت',
                                'desc': 'هر فایل به‌صورت جداگانه مجموعه‌ای در فایلینگ ایجاد می‌کند.',
                            },
                        ],
                        'tips': ['برای فایلینگ اولیه آژانس، bulk سریع‌ترین روش است.'],
                        'image': 'help-upload-bulk.png',
                        'image_caption': 'آپلود پوشه — انتخاب پوشه output ربات',
                        'url_name': 'workspace:dataset_bulk_upload',
                        'requires_bot': True,
                        'feature': 'upload',
                    },
                    {
                        'title': 'مدیریت مجموعه‌ها و جدول آگهی',
                        'icon': 'fa-table',
                        'steps': [
                            {
                                'title': 'لیست مجموعه‌ها',
                                'desc': 'همه فایل‌های آپلودشده با تاریخ، تعداد آگهی و نوع معامله نمایش داده می‌شوند.',
                            },
                            {
                                'title': 'جدول آگهی‌ها',
                                'desc': 'کلیک روی مجموعه → جدول با جستجو، فیلتر محله، مرتب‌سازی و export.',
                            },
                            {
                                'title': 'جزئیات آگهی',
                                'desc': 'کلیک روی هر ردیف → قیمت، امکانات، لینک دیوار، تبدیل به فایل شخصی.',
                            },
                            {
                                'title': 'عملیات گروهی',
                                'desc': 'حذف گروهی، export به CSV/JSON و حذف آگهی‌های مشاور.',
                            },
                        ],
                        'image': 'help-dataset-table.png',
                        'image_caption': 'جدول آگهی‌ها — فیلتر، مرتب‌سازی و export',
                        'url_name': 'workspace:dataset_list',
                        'requires_bot': True,
                        'feature': 'datasets',
                    },
                ],
            },
            {
                'id': 'market-analysis',
                'icon': 'fa-chart-line',
                'accent': 'emerald',
                'badge': 'bot',
                'title': 'تحلیل بازار و نقشه',
                'subtitle': 'آمار قیمت، نمودار، پیشنهادهای هوشمند، نقشه و مقایسه',
                'intro': (
                    'بعد از آپلود، تحلیل بازار تصویر دقیقی از قیمت‌ها، روندها و فرصت‌های '
                    'زیربازار همان محله به شما می‌دهد.'
                ),
                'topics': [
                    {
                        'title': 'داشبورد تحلیل بازار',
                        'icon': 'fa-chart-pie',
                        'steps': [
                            {
                                'title': 'ورود به تحلیل',
                                'desc': 'از کارت مجموعه → دکمه «تحلیل بازار».',
                            },
                            {
                                'title': 'آمار کلی',
                                'desc': 'میانه قیمت، میانگین متراژ، توزیع محله‌ها و نمودارهای تعاملی.',
                            },
                            {
                                'title': 'امتیاز ارزش',
                                'desc': 'آگهی‌های زیر یا بالای بازار با امتیاز تعدیل‌شده (سال ساخت، امکانات).',
                            },
                            {
                                'title': 'بینش مشاور',
                                'desc': 'کارت‌های تحلیلی برای تصمیم‌گیری سریع در مذاکره.',
                            },
                        ],
                        'tips': [
                            'برای رهن و اجاره، «اجاره معادل» در محاسبه امتیاز لحاظ می‌شود.',
                            'آگهی با اجاره صفر و رهن بالا = رهن کامل — نه الزاماً زیر بازار.',
                        ],
                        'image': 'help-analyze-dashboard.png',
                        'image_caption': 'صفحه تحلیل بازار — نمودارها، آمار و پیشنهادهای هوشمند',
                        'url_name': 'workspace:dataset_list',
                        'requires_bot': True,
                        'feature': 'analyze',
                    },
                    {
                        'title': 'نقشه آگهی‌ها',
                        'icon': 'fa-map-location-dot',
                        'steps': [
                            {
                                'title': 'نمای نقشه',
                                'desc': 'از مجموعه → «نقشه» — آگهی‌ها روی نقشه نمایش داده می‌شوند.',
                            },
                            {
                                'title': 'لایه حرارتی',
                                'desc': 'heatmap قیمت هر متر — مناطق گران‌تر و ارزان‌تر را ببینید.',
                            },
                            {
                                'title': 'خوشه‌بندی',
                                'desc': 'آگهی‌های نزدیک در خوشه جمع می‌شوند — برای zoom مناسب است.',
                            },
                            {
                                'title': 'تنظیمات نقشه',
                                'desc': 'از تنظیمات میزکار، cluster و heatmap را فعال/غیرفعال کنید.',
                            },
                        ],
                        'image': 'help-map-view.png',
                        'image_caption': 'نقشه آگهی‌ها — marker، heatmap و popup جزئیات',
                        'url_name': 'workspace:dataset_list',
                        'requires_bot': True,
                        'feature': 'map',
                    },
                    {
                        'title': 'مقایسه دو فایل',
                        'icon': 'fa-code-compare',
                        'steps': [
                            {
                                'title': 'انتخاب فایل‌ها',
                                'desc': 'منوی «مقایسه» → دو مجموعه (مثلاً این هفته و دو هفته قبل).',
                            },
                            {
                                'title': 'تغییرات قیمت',
                                'desc': 'آگهی‌های جدید، حذف‌شده و تغییر قیمت نمایش داده می‌شود.',
                            },
                            {
                                'title': 'تحلیل روند',
                                'desc': 'بفهمید بازار در حال رشد، ثبات یا افت است.',
                            },
                        ],
                        'tips': ['هر هفته یک مقایسه کوتاه، دید بهتری از رقبا می‌دهد.'],
                        'image': 'help-compare-files.png',
                        'image_caption': 'صفحه مقایسه — دو فایل کنار هم با تغییرات برجسته',
                        'url_name': 'workspace:compare',
                        'requires_bot': True,
                        'feature': 'compare',
                    },
                    {
                        'title': 'جزئیات آگهی و تبدیل به فایل شخصی',
                        'icon': 'fa-file-lines',
                        'steps': [
                            {
                                'title': 'صفحه جزئیات',
                                'desc': 'تمام فیلدها، امکانات، لینک دیوار و benchmark قیمت.',
                            },
                            {
                                'title': 'علاقه‌مندی',
                                'desc': 'آگهی را ستاره‌دار کنید تا بعداً سریع پیدا کنید.',
                            },
                            {
                                'title': 'تبدیل به فایل شخصی',
                                'desc': 'آگهی دیوار را به ملک CRM تبدیل کنید — برای تطبیق با مشتری.',
                            },
                        ],
                        'image': 'help-listing-detail.png',
                        'image_caption': 'جزئیات آگهی — benchmark، امکانات و دکمه تبدیل به فایل شخصی',
                        'requires_bot': True,
                        'feature': 'datasets',
                    },
                ],
            },
            {
                'id': 'smart-tools',
                'icon': 'fa-wand-magic-sparkles',
                'accent': 'cyan',
                'badge': 'bot',
                'title': 'ابزارهای هوشمند',
                'subtitle': 'محاسبه رهن و اجاره، قیمت هر متر و کمیسیون',
                'intro': 'ابزارهای روزمره مشاور — بدون نیاز به ماشین‌حساب جدا.',
                'topics': [
                    {
                        'title': 'تبدیل رهن و اجاره',
                        'icon': 'fa-exchange-alt',
                        'steps': [
                            {
                                'title': 'نرخ ۳۰:۱',
                                'desc': 'هر ۳۰ میلیون رهن ≈ ۱ میلیون اجاره — استاندارد بازار تهران.',
                            },
                            {
                                'title': 'تبدیل دوطرفه',
                                'desc': 'رهن به اجاره یا برعکس — برای مقایسه آگهی‌های مختلف.',
                            },
                        ],
                        'image': 'help-tools-panel.png',
                        'image_caption': 'ابزارهای هوشمند — تب تبدیل رهن و اجاره',
                        'url_name': 'workspace:tools',
                        'requires_bot': True,
                        'feature': 'tools',
                    },
                    {
                        'title': 'محاسبه قیمت هر متر',
                        'icon': 'fa-ruler-combined',
                        'steps': [
                            {
                                'title': 'قیمت کل → متر',
                                'desc': 'قیمت و متراژ را وارد کنید — قیمت هر متر محاسبه می‌شود.',
                            },
                            {
                                'title': 'متر → قیمت کل',
                                'desc': 'برای برآورد سریع ملک با دانستن نرخ محله.',
                            },
                        ],
                        'url_name': 'workspace:tools',
                        'requires_bot': True,
                        'feature': 'tools',
                    },
                    {
                        'title': 'محاسبه کمیسیون',
                        'icon': 'fa-percent',
                        'steps': [
                            {
                                'title': 'نوع معامله',
                                'desc': 'فروش، رهن یا اجاره — درصد کمیسیون متفاوت است.',
                            },
                            {
                                'title': 'تقسیم',
                                'desc': 'سهم مشاور، آژانس و طرف مقابل را ببینید.',
                            },
                        ],
                        'url_name': 'workspace:tools',
                        'requires_bot': True,
                        'feature': 'tools',
                    },
                ],
            },
            {
                'id': 'crm-overview',
                'icon': 'fa-gauge-high',
                'accent': 'violet',
                'badge': 'free',
                'title': 'داشبورد و صف کار CRM',
                'subtitle': 'نمای کلی فعالیت، کارهای امروز و جستجوی سراسری',
                'intro': (
                    'CRM میزکار کاملاً رایگان است. داشبورد مرکز فرمان روزانه شماست — '
                    'بدون نیاز به ربات.'
                ),
                'topics': [
                    {
                        'title': 'داشبورد CRM',
                        'icon': 'fa-gauge-high',
                        'steps': [
                            {
                                'title': 'خلاصه امروز',
                                'desc': 'تعداد تماس‌ها، بازدیدها، معاملات فعال و یادآورهای معوق.',
                            },
                            {
                                'title': 'نمودار فعالیت',
                                'desc': 'روند ثبت مخاطب و معامله در هفته اخیر.',
                            },
                            {
                                'title': 'دسترسی سریع',
                                'desc': 'لینک مستقیم به بخش‌های پرکاربرد.',
                            },
                        ],
                        'image': 'help-crm-dashboard.png',
                        'image_caption': 'داشبورد CRM — خلاصه فعالیت و کارهای معوق',
                        'url_name': 'workspace:crm_dashboard',
                    },
                    {
                        'title': 'صف کار امروز',
                        'icon': 'fa-list-check',
                        'steps': [
                            {
                                'title': 'اولویت‌بندی',
                                'desc': 'تماس‌ها و بازدیدهای امروز به ترتیب اهمیت.',
                            },
                            {
                                'title': 'تیک زدن',
                                'desc': 'بعد از انجام، مورد را complete کنید — از لیست حذف می‌شود.',
                            },
                            {
                                'title': 'معوق‌ها',
                                'desc': 'کارهای عقب‌افتاده با برچسب قرمز مشخص می‌شوند.',
                            },
                        ],
                        'image': 'help-crm-today.png',
                        'image_caption': 'صف کار امروز — لیست تماس و بازدید با اولویت',
                        'url_name': 'workspace:crm_today',
                    },
                    {
                        'title': 'جستجوی سراسری',
                        'icon': 'fa-magnifying-glass',
                        'steps': [
                            {
                                'title': 'میانبر Ctrl+K',
                                'desc': 'از هر صفحه‌ای جستجو را باز کنید.',
                            },
                            {
                                'title': 'جستجو در همه',
                                'desc': 'مخاطب، ملک، معامله و یادآور — یکجا.',
                            },
                        ],
                        'tips': ['سریع‌ترین راه رسیدن به هر رکورد در CRM.'],
                        'url_name': 'workspace:crm_contacts',
                    },
                ],
            },
            {
                'id': 'crm-contacts',
                'icon': 'fa-address-book',
                'accent': 'emerald',
                'badge': 'free',
                'title': 'مخاطبین و سرنخ‌ها',
                'subtitle': 'ثبت مشتری، برچسب، یادداشت، import و ادغام',
                'intro': 'قلب CRM — هر مشتری بالقوه و واقعی اینجا مدیریت می‌شود.',
                'topics': [
                    {
                        'title': 'ثبت مخاطب جدید',
                        'icon': 'fa-user-plus',
                        'steps': [
                            {
                                'title': 'ثبت سریع',
                                'desc': 'دکمه «+ مخاطب» در نمای کلی یا CRM → فرم کشویی.',
                            },
                            {
                                'title': 'اطلاعات پایه',
                                'desc': 'نام، موبایل، نوع (خریدار/فروشنده/مستاجر) و بودجه.',
                            },
                            {
                                'title': 'برچسب',
                                'desc': 'برچسب‌های رنگی برای دسته‌بندی — VIP، فوری، سرد و...',
                            },
                        ],
                        'image': 'help-crm-contacts.png',
                        'image_caption': 'لیست مخاطبین — فیلتر، برچسب و ثبت سریع',
                        'url_name': 'workspace:crm_contacts',
                        'url_query': 'open=drawer-contact',
                    },
                    {
                        'title': 'پروفایل و پیگیری',
                        'icon': 'fa-id-card',
                        'steps': [
                            {
                                'title': 'صفحه جزئیات',
                                'desc': 'تاریخچه تماس، یادداشت‌ها، املاک مرتبط و معاملات.',
                            },
                            {
                                'title': 'تطبیق هوشمند',
                                'desc': 'پیشنهاد ملک‌های مناسب بر اساس بودجه و نیاز مشتری.',
                            },
                            {
                                'title': 'یادآور',
                                'desc': 'تماس بعدی را با تاریخ و یادداشت تنظیم کنید.',
                            },
                        ],
                        'image': 'help-crm-contact-detail.png',
                        'image_caption': 'جزئیات مخاطب — تطبیق ملک، یادداشت و یادآور',
                        'url_name': 'workspace:crm_contacts',
                    },
                    {
                        'title': 'Import، Export و ادغام',
                        'icon': 'fa-file-import',
                        'steps': [
                            {
                                'title': 'Import از Excel',
                                'desc': 'لیست مشتریان قبلی را یک‌جا وارد کنید.',
                            },
                            {
                                'title': 'Export',
                                'desc': 'خروجی CSV برای پشتیبان یا انتقال.',
                            },
                            {
                                'title': 'ادغام تکراری',
                                'desc': 'دو مخاطب تکراری را merge کنید — تاریخچه حفظ می‌شود.',
                            },
                        ],
                        'url_name': 'workspace:crm_contacts',
                    },
                ],
            },
            {
                'id': 'crm-properties',
                'icon': 'fa-building',
                'accent': 'amber',
                'badge': 'free',
                'title': 'املاک شخصی',
                'subtitle': 'ثبت ملک، pipeline، تطبیق با مشتری و اشتراک تیمی',
                'intro': 'ملک‌های فایل شما — چه دستی ثبت شده چه از آگهی دیوار تبدیل شده.',
                'topics': [
                    {
                        'title': 'ثبت و مدیریت ملک',
                        'icon': 'fa-building',
                        'steps': [
                            {
                                'title': 'ثبت دستی',
                                'desc': 'از CRM → املاک → «ملک جدید» — آدرس، متراژ، قیمت و امکانات.',
                            },
                            {
                                'title': 'از آگهی دیوار',
                                'desc': 'در جزئیات آگهی → «تبدیل به فایل شخصی».',
                            },
                            {
                                'title': 'وضعیت',
                                'desc': 'فعال، رزرو، فروخته‌شده — pipeline قابل تنظیم.',
                            },
                        ],
                        'image': 'help-crm-properties.png',
                        'image_caption': 'لیست املاک — pipeline، فیلتر و وضعیت',
                        'url_name': 'workspace:crm_properties',
                    },
                    {
                        'title': 'تطبیق ملک–مشتری',
                        'icon': 'fa-link',
                        'steps': [
                            {
                                'title': 'از طرف ملک',
                                'desc': 'در جزئیات ملک → مشتریان پیشنهادی.',
                            },
                            {
                                'title': 'از طرف مشتری',
                                'desc': 'در پروفایل مخاطب → املاک مناسب.',
                            },
                        ],
                        'tips': ['بودجه و محله در تطبیق وزن بیشتری دارند.'],
                    },
                    {
                        'title': 'فیلترهای ذخیره‌شده',
                        'icon': 'fa-filter',
                        'steps': [
                            {
                                'title': 'ساخت فیلتر',
                                'desc': 'فیلتر کنید → «ذخیره فیلتر» — نام بگذارید.',
                            },
                            {
                                'title': 'پین کردن',
                                'desc': 'فیلتر پرکاربرد را pin کنید — همیشه در دسترس.',
                            },
                        ],
                    },
                ],
            },
            {
                'id': 'crm-deals',
                'icon': 'fa-handshake',
                'accent': 'cyan',
                'badge': 'free',
                'title': 'معاملات و قیف فروش',
                'subtitle': 'مراحل معامله، چک‌لیست، کمیسیون و پیگیری',
                'intro': 'از مذاکره اولیه تا عقد قرارداد — هر معامله را قدم‌به‌قدم دنبال کنید.',
                'topics': [
                    {
                        'title': 'ایجاد معامله',
                        'icon': 'fa-handshake',
                        'steps': [
                            {
                                'title': 'معامله جدید',
                                'desc': 'مشتری + ملک + مبلغ پیشنهادی را وصل کنید.',
                            },
                            {
                                'title': 'مرحله فعلی',
                                'desc': 'مذاکره، بازدید، پیش‌قرارداد، قرارداد نهایی.',
                            },
                        ],
                        'image': 'help-crm-deals.png',
                        'image_caption': 'قیف معاملات — Kanban مراحل و فیلتر',
                        'url_name': 'workspace:crm_deals',
                    },
                    {
                        'title': 'مراحل و چک‌لیست',
                        'icon': 'fa-list-check',
                        'steps': [
                            {
                                'title': 'سفارشی‌سازی مراحل',
                                'desc': 'CRM → معاملات → تنظیم مراحل — مطابق فرآیند آژانس.',
                            },
                            {
                                'title': 'چک‌لیست هر معامله',
                                'desc': 'مدارک، بازدید، تأیید مالک — تیک بزنید تا چیزی جا نماند.',
                            },
                        ],
                        'url_name': 'workspace:crm_deal_stages',
                    },
                    {
                        'title': 'کمیسیون',
                        'icon': 'fa-coins',
                        'steps': [
                            {
                                'title': 'ثبت کمیسیون',
                                'desc': 'مبلغ کل، سهم مشاور و آژانس.',
                            },
                            {
                                'title': 'وضعیت پرداخت',
                                'desc': 'دریافت‌شده، معوق یا جزئی.',
                            },
                        ],
                    },
                ],
            },
            {
                'id': 'crm-scheduling',
                'icon': 'fa-calendar-days',
                'accent': 'pink',
                'badge': 'free',
                'title': 'تقویم و یادآورها',
                'subtitle': 'برنامه‌ریزی بازدید، تماس و پیگیری',
                'intro': 'هیچ تماس و بازدیدی از قلم نمی‌افتد.',
                'topics': [
                    {
                        'title': 'تقویم CRM',
                        'icon': 'fa-calendar-days',
                        'steps': [
                            {
                                'title': 'نمای ماهانه/هفتگی',
                                'desc': 'همه رویدادها در یک نگاه.',
                            },
                            {
                                'title': 'رویداد جدید',
                                'desc': 'بازدید، جلسه یا تماس — با لینک به مخاطب/ملک.',
                            },
                        ],
                        'image': 'help-crm-calendar.png',
                        'image_caption': 'تقویم CRM — بازدیدها و تماس‌های برنامه‌ریزی‌شده',
                        'url_name': 'workspace:crm_calendar',
                    },
                    {
                        'title': 'یادآورها',
                        'icon': 'fa-bell',
                        'steps': [
                            {
                                'title': 'انواع یادآور',
                                'desc': 'تماس، بازدید، پیگیری قرارداد، تمدید.',
                            },
                            {
                                'title': 'یادآور معوق',
                                'desc': 'در داشبورد و صف کار با رنگ هشدار نمایش داده می‌شود.',
                            },
                        ],
                        'image': 'help-crm-reminders.png',
                        'image_caption': 'لیست یادآورها — امروز، آینده و معوق',
                        'url_name': 'workspace:crm_reminders',
                    },
                ],
            },
            {
                'id': 'crm-communication',
                'icon': 'fa-message',
                'accent': 'emerald',
                'badge': 'free',
                'title': 'قالب پیام و اتوماسیون',
                'subtitle': 'پیام‌های آماده واکنش‌گرا و قوانین خودکار',
                'intro': 'زمان پاسخ‌گویی را کوتاه کنید — بدون تایپ تکراری.',
                'topics': [
                    {
                        'title': 'قالب پیام',
                        'icon': 'fa-message',
                        'steps': [
                            {
                                'title': 'ساخت قالب',
                                'desc': 'متن با متغیرها — {نام}، {ملک}، {قیمت}.',
                            },
                            {
                                'title': 'ارسال سریع',
                                'desc': 'از پروفایل مخاطب → انتخاب قالب → کپی برای واتساپ.',
                            },
                            {
                                'title': 'پیش‌نمایش',
                                'desc': 'قبل از ارسال، متن نهایی را ببینید.',
                            },
                        ],
                        'image': 'help-crm-templates.png',
                        'image_caption': 'مدیریت قالب پیام — متغیرها و دسته‌بندی',
                        'url_name': 'workspace:crm_templates',
                    },
                    {
                        'title': 'اتوماسیون',
                        'icon': 'fa-bolt',
                        'steps': [
                            {
                                'title': 'تریگر',
                                'desc': 'وقتی مخاطب جدید ثبت شد / معامله مرحله عوض کرد /...',
                            },
                            {
                                'title': 'اقدام',
                                'desc': 'یادآور بساز، برچسب بزن، قالب پیام پیشنهاد بده.',
                            },
                        ],
                        'tips': ['با یک قانون ساده شروع کنید — مثلاً یادآور ۲۴ ساعته بعد از ثبت سرنخ.'],
                        'image': 'help-crm-automation.png',
                        'image_caption': 'اتوماسیون CRM — تریگر و اقدام',
                        'url_name': 'workspace:crm_automation',
                    },
                ],
            },
            {
                'id': 'crm-team',
                'icon': 'fa-users',
                'accent': 'violet',
                'badge': 'free',
                'title': 'تیم آژانس',
                'subtitle': 'اعضا، نقش‌ها، تخصیص مشتری و همگام‌سازی',
                'intro': 'برای آژانس‌های چند نفره — کار تیمی بدون تداخل.',
                'topics': [
                    {
                        'title': 'مدیریت اعضا',
                        'icon': 'fa-users',
                        'steps': [
                            {
                                'title': 'دعوت عضو',
                                'desc': 'ایمیل یا لینک دعوت — نقش مدیر، مشاور یا منشی.',
                            },
                            {
                                'title': 'سطوح دسترسی',
                                'desc': 'مدیر همه را می‌بیند؛ مشاور فقط مشتریان خود.',
                            },
                        ],
                        'image': 'help-crm-team.png',
                        'image_caption': 'صفحه تیم — اعضا، نقش‌ها و تخصیص',
                        'url_name': 'workspace:crm_team',
                    },
                    {
                        'title': 'تخصیص و انتقال',
                        'icon': 'fa-user-check',
                        'steps': [
                            {
                                'title': 'Assign',
                                'desc': 'مشتری جدید را به مشاور مشخص assign کنید.',
                            },
                            {
                                'title': 'Transfer',
                                'desc': 'مشتری را بین اعضا منتقل کنید — تاریخچه حفظ می‌شود.',
                            },
                        ],
                    },
                    {
                        'title': 'همگام‌سازی CRM',
                        'icon': 'fa-arrows-rotate',
                        'steps': [
                            {
                                'title': 'Export/Import',
                                'desc': 'پشتیبان CRM یا انتقال بین محیط‌ها.',
                            },
                            {
                                'title': 'اشتراک ملک',
                                'desc': 'ملک بین چند مشاور قابل مشاهده است.',
                            },
                        ],
                    },
                ],
            },
            {
                'id': 'workspace-settings',
                'icon': 'fa-sliders',
                'accent': 'sky',
                'badge': 'all',
                'title': 'تنظیمات میزکار',
                'subtitle': 'تم، فونت، نقشه و برندینگ آژانس',
                'intro': 'میزکار را مطابق سلیقه و هویت آژانس شخصی‌سازی کنید.',
                'topics': [
                    {
                        'title': 'ظاهر و خوانایی',
                        'icon': 'fa-palette',
                        'steps': [
                            {
                                'title': 'تم',
                                'desc': 'روشن، تاریک یا شاد — از نوار بالا یا تنظیمات.',
                            },
                            {
                                'title': 'مقیاس فونت',
                                'desc': 'برای نمایشگر بزرگ یا کوچک، اندازه متن را تنظیم کنید.',
                            },
                        ],
                        'image': 'help-settings-modal.png',
                        'image_caption': 'مودال تنظیمات — تم، فونت و گزینه‌های نقشه',
                        'url_name': 'workspace:home',
                        'url_query': 'open=modal-settings',
                    },
                    {
                        'title': 'نقشه و PDF',
                        'icon': 'fa-map',
                        'steps': [
                            {
                                'title': 'خوشه و heatmap',
                                'desc': 'فعال/غیرفعال از تنظیمات — روی همه نقشه‌ها اعمال می‌شود.',
                            },
                            {
                                'title': 'برندینگ PDF',
                                'desc': 'نام و لوگوی آژانس روی خروجی‌های PDF.',
                            },
                        ],
                    },
                ],
            },
        ],
        'faq': [
            {
                'q': 'آیا CRM میزکار رایگان است؟',
                'a': 'بله. مخاطبین، املاک شخصی، یادآورها، معاملات، تقویم، قالب پیام، اتوماسیون، تیم و داشبورد کاملاً رایگان است و نیازی به خرید ربات ندارد.',
            },
            {
                'q': 'ربات چه کاری می‌کند؟',
                'a': 'ربات آگهی‌های دیوار را روی ویندوز شما استخراج می‌کند و در پوشه output ذخیره می‌کند. خروجی را در فایلینگ میزکار آپلود کنید تا تحلیل، نقشه و مقایسه فعال شود.',
            },
            {
                'q': 'لایسنس را کجا فعال کنم؟',
                'a': 'کلید لایسنس را در نرم‌افزار ربات (تب لایسنس) وارد کنید — نه در وب. پس از فعال‌سازی، بخش‌های تحلیل در میزکار باز می‌شوند.',
            },
            {
                'q': 'چطور مشتری جدید ثبت کنم؟',
                'a': 'از «+ مخاطب» در نمای کلی، یا CRM → مخاطبین → ثبت سریع. نام، موبایل و نیاز را وارد کنید.',
            },
            {
                'q': 'تطبیق هوشمند ملک–مشتری چیست؟',
                'a': 'بر اساس بودجه، محله و نوع ملک، سیستم املاک مناسب را برای هر مشتری (و برعکس) پیشنهاد می‌دهد.',
            },
            {
                'q': 'آیا می‌توانم چند فایل را با هم مقایسه کنم؟',
                'a': 'در بخش مقایسه، دو مجموعه را انتخاب کنید — تغییرات قیمت، آگهی‌های جدید و حذف‌شده نمایش داده می‌شود.',
            },
            {
                'q': 'یادآور چطور کار می‌کند؟',
                'a': 'برای مخاطب یا ملک یادآور تماس/بازدید بگذارید. موارد امروز در صف کار و معوق‌ها در داشبورد با هشدار دیده می‌شوند.',
            },
            {
                'q': 'آپلود bulk چه تفاوتی با تکی دارد؟',
                'a': 'bulk کل پوشه output ربات را یک‌جا آپلود می‌کند — هر فایل یک مجموعه جدا. برای راه‌اندازی اولیه ایده‌آل است.',
            },
            {
                'q': 'تیم آژانس چند نفره پشتیبانی می‌شود؟',
                'a': 'بله. اعضا با نقش‌های مختلف، تخصیص مشتری، انتقال و اشتراک ملک — بدون نیاز به ربات.',
            },
        ],
    }
