from public_assistant.services.feature import widget_allowed_for_request


def public_assistant(request):
    return {
        'public_assistant_widget': widget_allowed_for_request(request),
    }
