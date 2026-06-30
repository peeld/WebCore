# Core signal handlers.
# Import this module only via CoreAppConfig.ready() — never import directly.

from django.dispatch import Signal

# Sent by billing when a payment succeeds and a license should be granted.
# kwargs: user (User instance), product_id (int), price_id (int),
#         stripe_payment_intent_id (str, optional),
#         stripe_subscription_id (str, optional)
license_grant_requested = Signal()
