# Core signal handlers.
# Import this module only via CoreAppConfig.ready() — never import directly.

from django.dispatch import Signal

# Sent by billing when a payment succeeds and a license should be granted.
# kwargs: user (User instance), product_id (int), price_id (int),
#         days_granted (int, optional — one-time purchase length; stacks expiry),
#         stripe_payment_intent_id (str, optional),
#         subscription_id (int, optional — local billing.Subscription pk; set for
#                          subscription grants so the license links to the sub)
license_grant_requested = Signal()

# Sent by billing when a subscription is cancelled and its licenses should be
# deactivated. Licensing deactivates every LicenseKey tied to the subscription.
# kwargs: subscription_id (int — local billing.Subscription pk)
license_revoke_requested = Signal()

# Sent by userauth when a user's email is confirmed. Other modules listen to
# attach records that were keyed on the email before an account existed
# (e.g. licensing links anonymous trial claims to the new account).
# kwargs: user (User instance)
email_verified = Signal()
