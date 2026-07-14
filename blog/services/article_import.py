"""درون‌ریزی مقاله از JSON — مشترک بین پنل مدیریت و ابزارهای CLI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

from blog.models import Category, Post
from blog.utils import get_or_create_tag, unique_post_slug

User = get_user_model()

FORMAT_VERSION = '1.0'
REQUIRED_ARTICLE_KEYS = ('slug_base', 'title', 'excerpt', 'category', 'tags', 'content')
REQUIRED_CATEGORY_KEYS = ('slug', 'name')


class ArticleImportError(Exception):
    """خطای اعتبارسنجی یا درون‌ریزی مقاله."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


@dataclass
class ArticleImportPreview:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    article: dict[str, Any] | None = None
    options: dict[str, Any] = field(default_factory=dict)
    existing_slug: str | None = None
    action: str = 'create'  # create | update | skip


def _ensure_str(value: Any, label: str, *, max_len: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArticleImportError(f'فیلد «{label}» باید متن غیرخالی باشد.', field=label)
    text = value.strip()
    if max_len is not None and len(text) > max_len:
        raise ArticleImportError(
            f'فیلد «{label}» حداکثر {max_len} کاراکتر مجاز است (فعلی: {len(text)}).',
            field=label,
        )
    return text


def _parse_payload(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ArticleImportError('بدنه JSON باید یک شیء (object) باشد.')

    version = raw.get('format_version') or raw.get('version')
    if version and str(version) != FORMAT_VERSION:
        raise ArticleImportError(
            f'نسخه فرمت پشتیبانی نمی‌شود: {version} (انتظار: {FORMAT_VERSION}).',
            field='format_version',
        )

    article = raw.get('article')
    if article is None and 'slug_base' in raw:
        article = raw
        options = {
            'publish': bool(raw.get('publish', raw.get('is_published', False))),
            'force_update': bool(raw.get('force_update', raw.get('force', False))),
            'author_username': raw.get('author_username', 'admin'),
        }
        return article, options

    if not isinstance(article, dict):
        raise ArticleImportError('فیلد «article» الزامی است.', field='article')

    options_raw = raw.get('options') or raw.get('import_options') or {}
    if not isinstance(options_raw, dict):
        raise ArticleImportError('فیلد «options» باید شیء باشد.', field='options')

    options = {
        'publish': bool(options_raw.get('publish', article.get('is_published', False))),
        'force_update': bool(options_raw.get('force_update', options_raw.get('force', False))),
        'author_username': str(
            options_raw.get('author_username')
            or article.get('author_username')
            or 'admin'
        ),
    }
    return article, options


def validate_article_payload(raw: dict[str, Any]) -> ArticleImportPreview:
    errors: list[str] = []
    warnings: list[str] = []
    article: dict[str, Any] | None = None
    options: dict[str, Any] = {}
    existing_slug: str | None = None
    action = 'create'

    try:
        article, options = _parse_payload(raw)
    except ArticleImportError as exc:
        return ArticleImportPreview(ok=False, errors=[str(exc)])

    assert article is not None

    for key in REQUIRED_ARTICLE_KEYS:
        if key not in article:
            errors.append(f'فیلد الزامی «article.{key}» موجود نیست.')

    if errors:
        return ArticleImportPreview(ok=False, errors=errors, article=article, options=options)

    try:
        slug_base = _ensure_str(article['slug_base'], 'slug_base', max_len=200)
        title = _ensure_str(article['title'], 'title', max_len=200)
        excerpt = _ensure_str(article['excerpt'], 'excerpt', max_len=300)
        content = _ensure_str(article['content'], 'content')

        category = article['category']
        if not isinstance(category, dict):
            raise ArticleImportError('article.category باید شیء باشد.', field='category')
        for key in REQUIRED_CATEGORY_KEYS:
            if key not in category:
                raise ArticleImportError(f'article.category.{key} الزامی است.', field=f'category.{key}')
        cat_slug = _ensure_str(category['slug'], 'category.slug', max_len=100)
        cat_name = _ensure_str(category['name'], 'category.name', max_len=100)

        tags = article['tags']
        if not isinstance(tags, list) or not tags:
            raise ArticleImportError('article.tags باید آرایه‌ای با حداقل یک برچسب باشد.', field='tags')
        tag_names = []
        for i, tag in enumerate(tags):
            if not isinstance(tag, str) or not tag.strip():
                raise ArticleImportError(f'برچسب #{i + 1} نامعتبر است.', field='tags')
            tag_names.append(tag.strip())

        if '<h2' not in content.lower() and '<h2>' not in content.lower():
            warnings.append('محتوا فاقد تگ <h2> است — مقالات حرفه‌ای معمولاً حداقل یک سرتیتر دارند.')
        if '<p' not in content.lower():
            warnings.append('محتوا فاقد پاراگراف HTML (<p>) است.')

        normalized = {
            'slug_base': slug_base,
            'title': title,
            'excerpt': excerpt,
            'content': content.strip(),
            'category': {
                'slug': cat_slug,
                'name': cat_name,
                'description': str(category.get('description') or '').strip(),
                'order': int(category.get('order') or 0),
            },
            'tags': tag_names,
            'keyword': str(article.get('keyword') or '').strip(),
        }
        article = normalized

        existing = Post.objects.filter(slug=slug_base).first()
        if existing:
            existing_slug = existing.slug
            if options.get('force_update'):
                action = 'update'
            else:
                action = 'skip'
                warnings.append(
                    f'مقاله با slug «{slug_base}» از قبل وجود دارد — برای بازنویسی force_update را فعال کنید.'
                )

    except ArticleImportError as exc:
        errors.append(str(exc))
    except (TypeError, ValueError) as exc:
        errors.append(f'ساختار JSON نامعتبر: {exc}')

    return ArticleImportPreview(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        article=article,
        options=options,
        existing_slug=existing_slug,
        action=action,
    )


def resolve_author(username: str):
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        author = User.objects.filter(is_superuser=True).order_by('pk').first()
        if not author:
            raise ArticleImportError('نویسنده یافت نشد و superuser در سیستم وجود ندارد.')
        return author


def import_article_from_payload(raw: dict[str, Any]) -> tuple[Post, str]:
    """
    مقاله را از JSON وارد می‌کند.

    Returns:
        (post, action) where action is 'created' | 'updated' | 'skipped'
    """
    preview = validate_article_payload(raw)
    if not preview.ok or preview.article is None:
        raise ArticleImportError(preview.errors[0] if preview.errors else 'JSON نامعتبر.')

    article = preview.article
    options = preview.options
    publish = options.get('publish', False)
    force = options.get('force_update', False)
    author = resolve_author(options.get('author_username', 'admin'))

    cat_data = article['category']
    category, _ = Category.objects.get_or_create(
        slug=cat_data['slug'],
        defaults={
            'name': cat_data['name'],
            'description': cat_data.get('description', ''),
            'order': cat_data.get('order', 0),
        },
    )

    tags = [get_or_create_tag(name) for name in article['tags']]

    slug_base = article['slug_base']
    existing = Post.objects.filter(slug=slug_base).first()
    slug = existing.slug if existing else unique_post_slug(slug_base)

    defaults = {
        'title': article['title'],
        'author': author,
        'category': category,
        'content': article['content'],
        'excerpt': article['excerpt'][:300],
        'is_published': publish,
        'published_at': timezone.now() if publish else None,
    }

    if existing and not force:
        existing.tags.set(tags)
        return existing, 'skipped'

    if existing:
        for key, val in defaults.items():
            setattr(existing, key, val)
        if publish and not existing.published_at:
            existing.published_at = timezone.now()
        existing.save()
        post = existing
        action = 'updated'
    else:
        post = Post.objects.create(slug=slug, **defaults)
        action = 'created'

    post.tags.set(tags)
    return post, action
