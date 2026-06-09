import logging

from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)


class CustomUser(AbstractUser):
    """Custom user model — extends AbstractUser with no additional fields initially.

    Always reference this via settings.AUTH_USER_MODEL rather than importing directly,
    so modules remain decoupled from this concrete class.
    """

    class Meta:
        db_table = 'core_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
