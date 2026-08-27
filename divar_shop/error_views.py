"""Custom HTTP error pages — بدون context processor و بدون وابستگی به DB."""
from django.http import HttpResponse
from django.template import loader


def _error_context(request, **extra):
    user = getattr(request, 'user', None)
    return {
        'path': request.get_full_path(),
        'is_workspace': request.path.startswith('/workspace/'),
        'user': user,
        'messages': [],
        **extra,
    }


def _render_error_page(request, template_name: str, status: int, **extra):
    """Render بدون request — context processorها (و کوئری DB) اجرا نمی‌شوند."""
    template = loader.get_template(template_name)
    html = template.render(_error_context(request, **extra))
    return HttpResponse(html, status=status, content_type='text/html; charset=utf-8')


def page_not_found(request, exception=None):
    return _render_error_page(request, 'errors/404.html', 404)


def server_error(request):
    return _render_error_page(request, 'errors/500.html', 500)


def permission_denied(request, exception=None):
    return _render_error_page(request, 'errors/403.html', 403)


def bad_request(request, exception=None):
    return _render_error_page(request, 'errors/400.html', 400)
