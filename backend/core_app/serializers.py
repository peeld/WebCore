from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


def _address_field(source):
    """CharField for a User address_* column, keeping the model's max_length
    (explicitly declared fields don't inherit it, so over-long input would
    otherwise reach the DB and 500)."""
    return serializers.CharField(
        source=source, allow_blank=True, required=False,
        max_length=User._meta.get_field(source).max_length,
    )


class UserAddressSerializer(serializers.ModelSerializer):
    """Exposes CustomUser's address_* fields under unprefixed names so the
    payload shape matches the address object billing's checkout already
    uses (name/street1/street2/city/state/zip/country/phone)."""

    name    = _address_field('address_name')
    street1 = _address_field('address_street1')
    street2 = _address_field('address_street2')
    city    = _address_field('address_city')
    state   = _address_field('address_state')
    zip     = _address_field('address_zip')
    country = _address_field('address_country')
    phone   = _address_field('address_phone')

    class Meta:
        model  = User
        fields = ['name', 'street1', 'street2', 'city', 'state', 'zip', 'country', 'phone']
