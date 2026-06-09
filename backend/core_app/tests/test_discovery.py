"""
Tests for the module auto-discovery system.
Uses temporary directories to simulate modules/ without touching real module files.
"""
import shutil
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from django.urls import reverse, NoReverseMatch

from core.settings.base import _discover_modules


class ModuleDiscoveryTests(SimpleTestCase):
    """Unit tests for _discover_modules() — no database required."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.modules_dir = self.tmp / "modules"
        self.modules_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)
        # Remove any tmp paths this test added to sys.path.
        sys.path = [p for p in sys.path if not str(self.tmp) in p]

    def _make_module(self, name):
        """Create a minimal valid module directory structure."""
        app_dir = self.modules_dir / name / "backend" / name
        app_dir.mkdir(parents=True)
        (app_dir / "apps.py").write_text("")
        return app_dir

    # ------------------------------------------------------------------

    def test_nonexistent_dir_returns_empty(self):
        result = _discover_modules(self.tmp / "nonexistent")
        self.assertEqual(result, [])

    def test_empty_modules_dir_returns_empty(self):
        result = _discover_modules(self.modules_dir)
        self.assertEqual(result, [])

    def test_valid_module_is_discovered(self):
        self._make_module("mymod")
        result = _discover_modules(self.modules_dir)
        self.assertIn("mymod", result)

    def test_module_without_apps_py_is_skipped(self):
        """A directory missing apps.py is not a valid Django app — ignore it."""
        (self.modules_dir / "broken" / "backend" / "broken").mkdir(parents=True)
        result = _discover_modules(self.modules_dir)
        self.assertNotIn("broken", result)

    def test_modules_returned_in_alphabetical_order(self):
        self._make_module("zebra")
        self._make_module("alpha")
        self._make_module("middle")
        result = _discover_modules(self.modules_dir)
        self.assertEqual(result, ["alpha", "middle", "zebra"])

    def test_backend_dir_added_to_sys_path(self):
        self._make_module("mymod")
        _discover_modules(self.modules_dir)
        expected = str(self.modules_dir / "mymod" / "backend")
        self.assertIn(expected, sys.path)

    def test_sys_path_not_duplicated_on_repeated_calls(self):
        self._make_module("mymod")
        _discover_modules(self.modules_dir)
        _discover_modules(self.modules_dir)
        expected = str(self.modules_dir / "mymod" / "backend")
        self.assertEqual(sys.path.count(expected), 1)

    def test_non_directory_entries_are_ignored(self):
        """Files at the top level of modules/ should not cause errors."""
        (self.modules_dir / "README.md").write_text("ignored")
        result = _discover_modules(self.modules_dir)
        self.assertEqual(result, [])


class InstalledModuleAppsTests(SimpleTestCase):
    """Verify INSTALLED_MODULE_APPS reflects currently installed modules."""

    def test_installed_module_apps_is_a_list(self):
        from django.conf import settings
        self.assertIsInstance(settings.INSTALLED_MODULE_APPS, list)

    def test_installed_module_apps_subset_of_installed_apps(self):
        from django.conf import settings
        for app in settings.INSTALLED_MODULE_APPS:
            self.assertIn(app, settings.INSTALLED_APPS)


class UrlDiscoveryTests(SimpleTestCase):
    """Integration tests — verify module URLs are (or aren't) registered."""

    def test_health_url_always_registered(self):
        """Core health endpoint must always resolve regardless of module state."""
        url = reverse("core_app:health")
        self.assertTrue(url.startswith("/api/"))

    @override_settings(INSTALLED_MODULE_APPS=["userauth"])
    def test_module_url_registered_when_in_installed_module_apps(self):
        """When userauth is in INSTALLED_MODULE_APPS its root URL must resolve."""
        # Re-import to pick up the overridden settings.
        # This tests the pattern rather than live URL routing (which is
        # computed at startup); a full integration test requires runserver.
        from core.urls import _module_urlpatterns
        patterns = _module_urlpatterns()
        prefixes = [str(p.pattern) for p in patterns]
        self.assertIn("api/userauth/", prefixes)

    @override_settings(INSTALLED_MODULE_APPS=[])
    def test_no_module_urls_when_list_empty(self):
        from core.urls import _module_urlpatterns
        patterns = _module_urlpatterns()
        self.assertEqual(patterns, [])
