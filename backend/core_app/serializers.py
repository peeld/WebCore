from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAddressSerializer(serializers.ModelSerializer):
    """Exposes CustomUser's address_* fields under unprefixed names so the
    payload shape matches the address object billing's checkout already
    uses (name/street1/street2/city/state/zip/country/phone)."""

    name    = serializers.CharField(source='address_name', allow_blank=True, required=False)
    street1 = serializers.CharField(source='address_street1', allow_blank=True, required=False)
    street2 = serializers.CharField(source='address_street2', allow_blank=True, required=False)
    city    = serializers.CharField(source='address_city', allow_blank=True, required=False)
    state   = serializers.CharField(source='address_state', allow_blank=True, required=False)
    zip     = serializers.CharField(source='address_zip', allow_blank=True, required=False)
    country = serializers.CharField(source='address_country', allow_blank=True, required=False)
    phone   = serializers.CharField(source='address_phone', allow_blank=True, required=False)

    class Meta:
        model  = User
        fields = ['name', 'street1', 'street2', 'city', 'state', 'zip', 'country', 'phone']
