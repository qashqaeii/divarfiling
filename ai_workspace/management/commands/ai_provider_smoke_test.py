"""Smoke test for AI HTTP providers (optional live call — skips without credentials)."""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError

from ai_workspace.providers.arvan import ArvanAIProvider, is_arvan_configured
from ai_workspace.providers.base import ProviderError


class Command(BaseCommand):
    help = 'Smoke test an AI provider with a minimal non-PII prompt (requires env credentials).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            default='arvan',
            choices=('arvan',),
            help='Provider to smoke test',
        )

    def handle(self, *args, **options):
        provider_name = options['provider']
        if provider_name != 'arvan':
            raise CommandError('Only arvan is supported in this smoke test.')

        if not is_arvan_configured():
            self.stdout.write(self.style.WARNING('Arvan not configured — skipping smoke test.'))
            return

        provider = ArvanAIProvider()
        started = time.perf_counter()
        try:
            result = provider.complete(
                system='You are a test assistant. Reply briefly.',
                user='Say exactly: OK',
            )
        except ProviderError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.stdout.write(
                f'provider=arvan status=fail code={exc.code} retryable={exc.retryable} '
                f'latency_ms={latency_ms}'
            )
            raise CommandError('Arvan smoke test failed') from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        self.stdout.write(
            self.style.SUCCESS(
                f'provider={result.provider} model={result.model} status=ok '
                f'latency_ms={latency_ms} input_tokens={result.input_tokens} '
                f'output_tokens={result.output_tokens} text_len={len(result.text or "")}'
            )
        )
