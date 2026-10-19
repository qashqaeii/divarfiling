"""بارگذاری/به‌روزرسانی دانشنامه از فایل‌های Markdown."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from public_assistant.models import KnowledgeArticle, KnowledgeChunk
from public_assistant.services.knowledge_loader import (
    article_content_hash,
    build_search_blob,
    chunk_body,
    iter_article_files,
    parse_markdown_file,
)


class Command(BaseCommand):
    help = 'Sync public knowledge articles from markdown files into the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate and report without writing to DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        paths = list(iter_article_files())
        if not paths:
            raise CommandError('No markdown articles found.')

        seen_ids: set[str] = set()
        parsed_items: list[tuple] = []
        errors: list[str] = []

        for path in paths:
            try:
                parsed = parse_markdown_file(path)
            except ValueError as exc:
                errors.append(f'{path}: {exc}')
                continue

            meta = parsed.meta
            article_id = str(meta['id'])
            if article_id in seen_ids:
                errors.append(f'Duplicate id {article_id} in {path}')
                continue
            seen_ids.add(article_id)
            parsed_items.append((path, parsed))

        if errors:
            for line in errors:
                self.stderr.write(self.style.ERROR(f'ERROR {line}'))
            raise CommandError(f'{len(errors)} validation error(s); sync aborted with no DB changes.')

        if dry_run:
            for path, parsed in parsed_items:
                self.stdout.write(f'OK {parsed.meta["id"]} ({path.name})')
            self.stdout.write(self.style.SUCCESS(f'Validated {len(parsed_items)} files.'))
            return

        created = updated = unchanged = 0

        with transaction.atomic():
            for path, parsed in parsed_items:
                meta = parsed.meta
                article_id = str(meta['id'])
                body = parsed.body
                chash = article_content_hash(meta, body)
                reviewed = meta.get('reviewed_at')
                reviewed_date = parse_date(str(reviewed)) if reviewed else None

                fields = {
                    'title': meta['title'],
                    'category': meta['category'],
                    'summary': meta.get('summary') or '',
                    'body_markdown': body,
                    'prerequisites': meta.get('prerequisites') or '',
                    'platforms': meta.get('platforms') or [],
                    'subscription_note': meta.get('subscription_note') or '',
                    'limitations': meta.get('limitations') or '',
                    'synonyms': meta.get('synonyms') or [],
                    'related_links': meta.get('links') or meta.get('related_links') or [],
                    'technical_refs': meta.get('technical_refs') or meta.get('sources') or [],
                    'reviewed_at': reviewed_date,
                    'source_path': parsed.source_path,
                    'content_hash': chash,
                    'is_public': bool(meta.get('is_public', True)),
                    'is_active': bool(meta.get('is_active', True)),
                }

                obj, was_created = KnowledgeArticle.objects.get_or_create(
                    article_id=article_id,
                    defaults=fields,
                )
                if was_created:
                    created += 1
                elif obj.content_hash != chash:
                    for k, v in fields.items():
                        setattr(obj, k, v)
                    obj.save()
                    updated += 1
                else:
                    unchanged += 1
                    continue

                obj.chunks.all().delete()
                for idx, (heading, chunk_body_text) in enumerate(chunk_body(body)):
                    KnowledgeChunk.objects.create(
                        article=obj,
                        chunk_index=idx,
                        heading=heading,
                        body=chunk_body_text,
                        search_blob=build_search_blob(meta, heading, chunk_body_text),
                    )

            stale = KnowledgeArticle.objects.exclude(article_id__in=seen_ids)
            deactivated = stale.update(is_active=False)
            if deactivated:
                self.stdout.write(f'Deactivated {deactivated} articles missing from source files.')

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. created={created} updated={updated} unchanged={unchanged}'
            )
        )
