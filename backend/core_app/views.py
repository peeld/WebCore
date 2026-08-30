import logging

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserAddressSerializer

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


class UserAddressView(APIView):
    """Get or update the authenticated user's single saved shipping address."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserAddressSerializer(request.user).data)

    def patch(self, request):
        serializer = UserAddressSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info('Address updated for user %s', request.user.pk)
        return Response(serializer.data)
