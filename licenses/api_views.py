"""
API Views برای لایسنس — لایه نازک روی services/api
"""
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from licenses.permissions import BotLicenseAPIPermission
from licenses.services.api import LicenseAPIError, activate_license, deactivate_license, validate_license
from licenses.services.bot_import import import_dataset_for_bot


def _error_response(exc: LicenseAPIError) -> Response:
    payload = {'error': exc.message}
    payload.update(exc.payload)
    return Response(payload, status=exc.http_status)


@method_decorator(csrf_exempt, name='dispatch')
class ActivateLicenseView(APIView):
    permission_classes = [BotLicenseAPIPermission]

    def post(self, request):
        try:
            return Response(activate_license(request))
        except LicenseAPIError as exc:
            return _error_response(exc)


@method_decorator(csrf_exempt, name='dispatch')
class ValidateLicenseView(APIView):
    permission_classes = [BotLicenseAPIPermission]

    def post(self, request):
        try:
            return Response(validate_license(request))
        except LicenseAPIError as exc:
            return _error_response(exc)


@method_decorator(csrf_exempt, name='dispatch')
class DeactivateLicenseView(APIView):
    permission_classes = [BotLicenseAPIPermission]

    def post(self, request):
        try:
            return Response(deactivate_license(request))
        except LicenseAPIError as exc:
            return _error_response(exc)


@method_decorator(csrf_exempt, name='dispatch')
class BotDatasetImportView(APIView):
    permission_classes = [BotLicenseAPIPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            return Response(import_dataset_for_bot(request))
        except LicenseAPIError as exc:
            return _error_response(exc)
