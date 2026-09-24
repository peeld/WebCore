"""Sentry helpers for the Django backend."""
import sentry_sdk


class SentryUserMiddleware:
    """Attach the authenticated user's id and username to Sentry events.

    send_default_pii stays False (no IP, cookies or email), so the Django
    integration won't add the user itself. request.user is read lazily when
    an event is captured rather than here: JWT auth happens inside DRF views,
    which then write the authenticated user back onto the Django request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        def add_user(event, hint):
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated:
                event.setdefault('user', {}).update(
                    {'id': str(user.pk), 'username': user.get_username()}
                )
            return event

        # A fresh scope per request so the processor can't leak into
        # events from later requests handled by the same thread.
        with sentry_sdk.new_scope() as scope:
            scope.add_event_processor(add_user)
            return self.get_response(request)
