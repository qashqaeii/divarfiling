"""بارگذاری و اعتبارسنجی مقالات Markdown."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yaml

from django.conf import settings

from public_assistant.constants import CHUNK_MAX_CHARS
from public_assistant.services.persian_text import normalize_persian

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)$', re.DOTALL)
_HEADING_RE = re.compile(r'^##\s+(.+)$', re.MULTILINE)


@dataclass
class ParsedArticle:
    meta: dict[str, Any]
    body: str
    source_path: str


def knowledge_articles_dir() -> Path:
    return Path(settings.BASE_DIR) / 'public_assistant' / 'knowledge' / 'articles'


def _content_hash(meta: dict, body: str) -> str:
    payload = yaml.safe_dump(meta, sort_keys=True, allow_unicode=True) + '\n' + body
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def parse_markdown_file(path: Path) -> ParsedArticle:
    raw = path.read_text(encoding='utf-8')
    match = _FRONTMATTER_RE.match(raw.strip())
    if not match:
        raise ValueError(f'frontmatter missing: {path}')
    meta = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    required = ('id', 'title', 'category')
    for key in required:
        if not meta.get(key):
            raise ValueError(f'missing {key} in {path}')
    return ParsedArticle(meta=meta, body=body, source_path=str(path.relative_to(settings.BASE_DIR)))


def iter_article_files() -> Iterator[Path]:
    root = knowledge_articles_dir()
    if not root.is_dir():
        return iter(())
    return sorted(root.glob('*.md'))


def chunk_body(body: str) -> list[tuple[str, str]]:
    """تقسیم بر اساس ## یا اندازه."""
    sections: list[tuple[str, str]] = []
    parts = _HEADING_RE.split(body)
    if len(parts) == 1:
        text = parts[0].strip()
        if text:
            sections.append(('', text))
    else:
        preamble = parts[0].strip()
        if preamble:
            sections.append(('', preamble))
        i = 1
        while i < len(parts):
            heading = parts[i].strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ''
            if content:
                sections.append((heading, content))
            i += 2

    chunks: list[tuple[str, str]] = []
    for heading, content in sections:
        if len(content) <= CHUNK_MAX_CHARS:
            chunks.append((heading, content))
            continue
        start = 0
        part = 0
        while start < len(content):
            piece = content[start : start + CHUNK_MAX_CHARS]
            suffix = f' (بخش {part + 1})' if part else ''
            chunks.append((heading + suffix, piece))
            start += CHUNK_MAX_CHARS
            part += 1
    return chunks or [('', body[:CHUNK_MAX_CHARS])]


def build_search_blob(article_meta: dict, heading: str, body: str) -> str:
    bits = [
        article_meta.get('title') or '',
        article_meta.get('summary') or '',
        ' '.join(article_meta.get('synonyms') or []),
        heading,
        body,
    ]
    return normalize_persian('\n'.join(bits))


def article_content_hash(meta: dict, body: str) -> str:
    return _content_hash(meta, body)
