from django.test import TestCase
from django.urls import reverse

from core_app.views import VERSION


class HealthCheckTests(TestCase):

    def test_returns_200(self):
        response = self.client.get(reverse('core_app:health'))
        self.assertEqual(response.status_code, 200)

    def test_returns_json_status_ok(self):
        response = self.client.get(reverse('core_app:health'))
        data = response.json()
        self.assertEqual(data['status'], 'ok')

    def test_returns_version(self):
        response = self.client.get(reverse('core_app:health'))
        data = response.json()
        self.assertEqual(data['version'], VERSION)

    def test_unauthenticated_access_allowed(self):
        """Health check must be reachable without credentials for deployment pipeline."""
        response = self.client.get(reverse('core_app:health'))
        self.assertNotEqual(response.status_code, 403)
