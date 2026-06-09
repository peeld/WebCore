import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

VERSION = '0.1.0'


class HealthCheckView(APIView):
    """Returns service status and version.

    Used by the deployment pipeline to verify a successful deploy.
    Intentionally unauthenticated so the pipeline doesn't need credentials.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        logger.debug("Health check requested from %s", request.META.get('REMOTE_ADDR'))
        return Response({'status': 'ok', 'version': VERSION})
