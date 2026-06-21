"""Custom HTTP error pages — lightweight, DB-safe templates."""
from django.shortcuts import render


def _error_context(request, **extra):
    return {
        'path': request.get_full_path(),
        'is_workspace': request.path.startswith('/workspace/'),
        **extra,
    }


def page_not_found(request, exception=None):
    return render(request, 'errors/404.html', _error_context(request), status=404)


def server_error(request):
    return render(request, 'errors/500.html', _error_context(request), status=500)


def permission_denied(request, exception=None):
    return render(request, 'errors/403.html', _error_context(request), status=403)


def bad_request(request, exception=None):
    return render(request, 'errors/400.html', _error_context(request), status=400)
