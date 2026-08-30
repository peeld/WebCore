from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Custom user model — extends AbstractUser with a single optional saved
    shipping address (used today by billing checkout; kept here rather than
    in a module since it's shared account data any module could use).

    Always reference this via settings.AUTH_USER_MODEL rather than importing directly,
    so modules remain decoupled from this concrete class.
    """

    address_name    = models.CharField(max_length=255, blank=True)
    address_street1 = models.CharField(max_length=255, blank=True)
    address_street2 = models.CharField(max_length=255, blank=True)
    address_city    = models.CharField(max_length=100, blank=True)
    address_state   = models.CharField(max_length=100, blank=True)
    address_zip     = models.CharField(max_length=20, blank=True)
    address_country = models.CharField(max_length=2, blank=True)
    address_phone   = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = 'core_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
