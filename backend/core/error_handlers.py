import logging

from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """DRF exception handler: passes known API exceptions through normally,
    and converts any unhandled Python exception into a JSON 500 instead of
    letting it bubble up to Django's HTML error page."""
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception('Unhandled exception in API view: %s', exc)
        return Response({'error': 'An unexpected server error occurred.'}, status=500)
    return response


def handler404(request, exception):
    if request.path.startswith('/api/'):
        return JsonResponse({'error': 'Not found.'}, status=404)
    from django.views.defaults import page_not_found
    return page_not_found(request, exception)


def handler500(request):
    if request.path.startswith('/api/'):
        return JsonResponse({'error': 'Server error.'}, status=500)
    from django.views.defaults import server_error
    return server_error(request)
