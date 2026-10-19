"""یک‌بار یا پس از ویرایش seed، فایل‌های .md را بازتولید می‌کند."""
from __future__ import annotations

from pathlib import Path

import yaml

from public_assistant.knowledge.article_seed import ARTICLES


def main():
    out_dir = Path(__file__).resolve().parent / 'articles'
    out_dir.mkdir(parents=True, exist_ok=True)
    for item in ARTICLES:
        meta = {k: v for k, v in item.items() if k != 'body'}
        body = item['body']
        text = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n\n' + body + '\n'
        path = out_dir / f"{meta['id']}.md"
        path.write_text(text, encoding='utf-8')
    print(f'Wrote {len(ARTICLES)} articles to {out_dir}')


if __name__ == '__main__':
    main()
