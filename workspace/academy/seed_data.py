"""داده seed آکادمی — Curriculum فعال: ۲ مسیر، ۸ ویدیو."""
from __future__ import annotations

PATHS = [
    {
        'slug': 'getting-started',
        'title': 'شروع کار با فایلینگ دیوار',
        'icon': 'fa-rocket',
        'description': 'از اینجا شروع کن؛ ابتدا با فایلینگ دیوار، داشبورد و نحوه خرید و فعال‌سازی لایسنس آشنا شو.',
        'order': 0,
        'is_public': True,
        'phase': 'launch',
    },
    {
        'slug': 'extracting-and-managing-files',
        'title': 'استخراج و مدیریت فایل‌ها',
        'icon': 'fa-folder-open',
        'description': 'از استخراج آگهی تا بررسی فایل، فایل‌های شخصی، نقشه، کمد و زونکن را قدم‌به‌قدم یاد بگیر.',
        'order': 1,
        'is_public': True,
        'phase': 'launch',
    },
]

# slugهای Curriculum فعال — برای پاک‌سازی DB
CURRICULUM_VIDEO_SLUGS = (
    'academy-what-is-divar-filing',
    'academy-dashboard-overview',
    'academy-license-purchase-activation',
    'academy-extract-divar-listings',
    'academy-filter-files',
    'academy-review-analyze-file',
    'academy-personal-files-map',
    'academy-file-cabinets-folders',
)

LEGACY_PATH_SLUGS = (
    'intro', 'quick-start', 'filing', 'crm', 'data', 'agency',
)

VIDEOS = [
    {
        'path_slug': 'getting-started',
        'order': 1,
        'slug': 'academy-what-is-divar-filing',
        'title': 'فایلینگ دیوار دقیقاً چه کاری انجام می‌دهد؟',
        'description': (
            'در این آموزش با فایلینگ دیوار و بخش‌های اصلی آن آشنا می‌شوید و می‌بینید '
            'چطور می‌توانید فایل‌ها و فرایند کاری خود را منظم‌تر مدیریت کنید.'
        ),
        'subtitle': 'شناخت کلی فایلینگ دیوار و کاربرد آن برای مشاور املاک',
        'file_name': 'what_can_divar_filing_do_for_you.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/what_can_divar_filing_do_for_you.webp',
        'duration_seconds': 76,
        'is_public': True,
        'action_url': '',
        'action_label': '',
        'next_cta': 'آموزش بعدی: معرفی داشبورد',
    },
    {
        'path_slug': 'getting-started',
        'order': 2,
        'slug': 'academy-dashboard-overview',
        'title': 'معرفی داشبورد و بخش‌های اصلی',
        'description': (
            'در این آموزش داشبورد فایلینگ دیوار و بخش‌های اصلی میزکار را بررسی می‌کنیم '
            'تا قبل از شروع کار با امکانات تخصصی، مسیرها و ابزارهای اصلی را بشناسید.'
        ),
        'subtitle': 'آشنایی با محیط کار فایلینگ دیوار',
        'file_name': 'Introduction_to_the_Dashboard_and_Main_Sections.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/Introduction_to_the_Dashboard_and_Main_Sections.webp',
        'duration_seconds': 92,
        'is_public': True,
        'action_url': '/workspace/',
        'action_label': 'ورود به میزکار',
        'next_cta': 'آموزش بعدی: خرید و فعال‌سازی لایسنس',
    },
    {
        'path_slug': 'getting-started',
        'order': 3,
        'slug': 'academy-license-purchase-activation',
        'title': 'خرید و فعال‌سازی لایسنس',
        'description': (
            'در این آموزش یاد می‌گیرید چگونه لایسنس مناسب را انتخاب، خرید و فعال کنید '
            'و تفاوت گزینه‌های خرید را بهتر بشناسید.'
        ),
        'subtitle': 'فعال‌سازی صحیح لایسنس و آماده شدن برای شروع کار',
        'file_name': 'Purchasing_and_Activating_a_License.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/Purchasing_and_Activating_a_License.webp',
        'duration_seconds': 96,
        'is_public': True,
        'action_url': '/shop/',
        'action_label': 'مشاهده پلن‌ها و خرید',
        'next_cta': 'شروع استخراج فایل‌ها',
    },
    {
        'path_slug': 'extracting-and-managing-files',
        'order': 1,
        'slug': 'academy-extract-divar-listings',
        'title': 'استخراج سریع آگهی‌های دیوار',
        'description': (
            'در این آموزش یاد می‌گیرید چگونه آگهی‌های موردنظر خود را از دیوار استخراج '
            'و وارد فایلینگ دیوار کنید.'
        ),
        'subtitle': 'استخراج و ورود آگهی‌ها به فایلینگ دیوار',
        'file_name': 'Extracting-Divar-Listings-in-Less-Than-Two-Minutes.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/Extracting-Divar-Listings-in-Less-Than-Two-Minutes.webp',
        'duration_seconds': 234,
        'is_public': True,
        'action_url': '/workspace/datasets/',
        'action_label': 'رفتن به فایل‌های استخراج',
        'next_cta': 'آموزش بعدی: فیلتر کردن فایل‌ها',
    },
    {
        'path_slug': 'extracting-and-managing-files',
        'order': 2,
        'slug': 'academy-filter-files',
        'title': 'فیلتر کردن فایل‌ها',
        'description': (
            'یاد بگیرید فایل‌ها را بر اساس معیارهای موردنظر فیلتر کنید '
            'تا سریع‌تر به فایل مناسب برسید.'
        ),
        'subtitle': 'کاهش زمان جستجو و رسیدن سریع‌تر به فایل مناسب',
        'file_name': 'Filtering-Files.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/Filtering-Files.webp',
        'duration_seconds': 122,
        'is_public': True,
        'action_url': '/workspace/listings/',
        'action_label': 'جستجو و فیلتر آگهی‌ها',
        'next_cta': 'آموزش بعدی: بررسی و تحلیل یک فایل',
    },
    {
        'path_slug': 'extracting-and-managing-files',
        'order': 3,
        'slug': 'academy-review-analyze-file',
        'title': 'بررسی و تحلیل یک فایل',
        'description': (
            'در این آموزش بخش‌های مختلف یک فایل را بررسی می‌کنیم '
            'تا قبل از تماس یا پیگیری، اطلاعات مهم فایل را سریع‌تر تحلیل کنید.'
        ),
        'subtitle': 'شناخت کامل اطلاعات یک فایل قبل از اقدام',
        'file_name': 'Reviewing-and-Analyzing-a-File.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/Reviewing-and-Analyzing-a-File.webp',
        'duration_seconds': 188,
        'is_public': True,
        'action_url': '/workspace/listings/',
        'action_label': 'مشاهده آگهی‌ها',
        'next_cta': 'آموزش بعدی: فایل‌های شخصی و نقشه',
    },
    {
        'path_slug': 'extracting-and-managing-files',
        'order': 4,
        'slug': 'academy-personal-files-map',
        'title': 'افزودن فایل به فایل‌های شخصی و کار با نقشه',
        'description': (
            'یاد می‌گیرید فایل‌های مهم را به فایل‌های شخصی اضافه کنید '
            'و موقعیت و فایل‌های خود را از طریق نقشه مدیریت کنید.'
        ),
        'subtitle': 'ساخت بانک شخصی فایل و استفاده از نقشه',
        'file_name': 'Adding-Files-to-Personal-Files-and-Using-the-Map.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/Adding-Files-to-Personal-Files-and-Using-the-Map.webp',
        'duration_seconds': 283,
        'is_public': True,
        'action_url': '/workspace/crm/properties/',
        'action_label': 'فایل‌های شخصی',
        'next_cta': 'آموزش بعدی: زونکن و کمد فایل‌ها',
    },
    {
        'path_slug': 'extracting-and-managing-files',
        'order': 5,
        'slug': 'academy-file-cabinets-folders',
        'title': 'مدیریت زونکن و کمد فایل‌ها',
        'description': (
            'در این آموزش یاد می‌گیرید با کمد و زونکن، فایل‌های شخصی خود را مرتب و دسته‌بندی کنید '
            'تا هر فایل را سریع پیدا کنید.'
        ),
        'subtitle': 'ساخت ساختار منظم برای مدیریت فایل‌های شخصی',
        'file_name': 'Managing-File-Cabinets-and-Folders.mp4',
        'file_path': 'Video',
        'poster_path': 'academy/posters/Managing-File-Cabinets-and-Folders.webp',
        'duration_seconds': 135,
        'is_public': True,
        'action_url': '/workspace/',
        'action_label': 'ورود به فایلینگ دیوار',
        'next_cta': '',
    },
]

CONTEXTUAL_BANNERS = {
    'listings_empty': {
        'video_slug': 'academy-extract-divar-listings',
        'title': 'هنوز فایلی ندارید؟',
        'message': 'در چند دقیقه یاد بگیرید چطور آگهی‌های دیوار را استخراج کنید',
    },
    'datasets_empty': {
        'video_slug': 'academy-extract-divar-listings',
        'title': 'اولین استخراج را شروع کنید',
        'message': 'آموزش استخراج سریع آگهی‌های دیوار',
    },
    'properties_empty': {
        'video_slug': 'academy-personal-files-map',
        'title': 'فایل شخصی بسازید',
        'message': 'یاد بگیرید فایل را به فایل‌های شخصی اضافه کنید و روی نقشه ببینید',
    },
}
