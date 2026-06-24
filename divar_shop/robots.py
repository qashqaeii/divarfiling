"""
robots.txt داینامیک — مسیرهای خصوصی را از ایندکس خارج می‌کند.
ربات‌های OpenAI (OAI-SearchBot, GPTBot, ChatGPT-User) صریحاً مجازند.
"""
from django.conf import settings
from django.http import HttpResponse

# مسیرهایی که نباید ایندکس شوند (همه crawlerها)
_PRIVATE_DISALLOW = (
    '/admin/',
    '/accounts/',
    '/workspace/',
    '/api/',
    '/payment/',
    '/affiliate/',
    '/products/*/buy/',
    '/products/*/apply-discount/',
    '/products/*/rating/',
    '/products/*/review/',
    '/reviews/',
)

# User-agentهای OpenAI — برای ChatGPT Search و crawling
_OPENAI_AGENTS = (
    'OAI-SearchBot',
    'GPTBot',
    'ChatGPT-User',
)


def _agent_block(user_agent: str) -> list[str]:
    lines = [f'User-agent: {user_agent}', 'Allow: /', '']
    for path in _PRIVATE_DISALLOW:
        lines.append(f'Disallow: {path}')
    lines.append('')
    return lines


def robots_txt(request):
    site_url = getattr(settings, 'SITE_URL', 'https://divarfiling.ir').rstrip('/')

    lines: list[str] = []
    for agent in _OPENAI_AGENTS:
        lines.extend(_agent_block(agent))

    lines.extend([
        'User-agent: *',
        'Allow: /',
        '',
    ])
    for path in _PRIVATE_DISALLOW:
        lines.append(f'Disallow: {path}')
    lines.append('')
    lines.append(f'Sitemap: {site_url}/sitemap.xml')

    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
