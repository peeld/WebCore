"""
core/emails.py — Shared email infrastructure for all modules.

Usage:
    from core.emails import send_email, base_html
"""

import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def base_html(title, content):
    """Wrap content in the standard branded HTML email shell."""
    app_name = getattr(settings, 'APP_NAME', 'App')
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#0a1628;font-family:'Inter',system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a1628;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="padding:0 0 32px 0;text-align:center;">
              <span style="font-size:22px;font-weight:700;color:#ffffff;">
                {app_name}
              </span>
            </td>
          </tr>

          <!-- Card -->
          <tr>
            <td style="background:#112240;border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:40px;">
              {content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 0 0 0;text-align:center;">
              <p style="color:#8899aa;font-size:12px;margin:0;">
                &copy; 2026 Peel Software Development LLC - All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _get_ses_client():
    access_key = getattr(settings, 'AWS_SES_ACCESS_KEY', None)
    secret_key = getattr(settings, 'AWS_SES_SECRET_KEY', None)
    region = getattr(settings, 'AWS_SES_REGION_NAME', 'us-east-1')

    if not access_key or not secret_key:
        raise ImproperlyConfigured(
            'AWS_SES_ACCESS_KEY and AWS_SES_SECRET_KEY must be set in Django settings.'
        )

    return boto3.client(
        'ses',
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def send_email(to, subject, text_body, html_body):
    """
    Send an email via AWS SES using boto3.

    Raises:
        ImproperlyConfigured: If SES credentials or DEFAULT_FROM_EMAIL are missing.
        ValueError: If 'to' is empty or wrong type.
    """
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    if not from_email:
        raise ImproperlyConfigured(
            'DEFAULT_FROM_EMAIL is not configured. Set it in Django settings.'
        )

    if isinstance(to, str):
        recipients = [to]
    elif isinstance(to, (list, tuple)):
        recipients = list(to)
    else:
        raise ValueError(f'Invalid recipient type: {type(to)}. Expected str or list.')

    if not recipients:
        raise ValueError('Recipient list cannot be empty.')

    try:
        client = _get_ses_client()
        response = client.send_email(
            Source=from_email,
            Destination={'ToAddresses': recipients},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                },
            },
        )
        message_id = response.get('MessageId')
        logger.info('Email sent via SES', extra={'subject': subject, 'to': recipients, 'message_id': message_id})
        return message_id

    except (ImproperlyConfigured, ValueError):
        raise

    except ClientError as e:
        logger.error(
            'SES ClientError sending email: %s',
            e.response['Error']['Message'],
            extra={'subject': subject, 'recipients': recipients},
            exc_info=True,
        )
        raise

    except BotoCoreError as e:
        logger.error(
            'BotoCoreError sending email: %s',
            e,
            extra={'subject': subject, 'recipients': recipients},
            exc_info=True,
        )
        raise
