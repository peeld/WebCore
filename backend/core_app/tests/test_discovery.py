"""
Tests for the module auto-discovery system.
Uses temporary directories to simulate modules/ without touching real module files.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from core.settings.base import _discover_modules, _topo_sort


class ModuleDiscoveryTests(SimpleTestCase):
    """Unit tests for _discover_modules() -- no database required."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.modules_dir = self.tmp / "modules"
        self.modules_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)
        sys.path = [p for p in sys.path if str(self.tmp) not in p]

    def _make_module(self, name, requires=None):
        """Create a minimal valid module directory structure.

        Writes module.json with `requires` when provided.
        """
        app_dir = self.modules_dir / name / "backend" / name
        app_dir.mkdir(parents=True)
        (app_dir / "apps.py").write_text("")
        if requires is not None:
            manifest = {"name": name, "version": "1.0.0", "requires": requires}
            (self.modules_dir / name / "module.json").write_text(json.dumps(manifest))
        return app_dir

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
        """A directory missing apps.py is not a valid Django app -- ignore it."""
        (self.modules_dir / "broken" / "backend" / "broken").mkdir(parents=True)
        result = _discover_modules(self.modules_dir)
        self.assertNotIn("broken", result)

    def test_modules_without_requires_returned_in_alphabetical_order(self):
        self._make_module("zebra")
        self._make_module("alpha")
        self._make_module("middle")
        result = _discover_modules(self.modules_dir)
        self.assertEqual(result, ["alpha", "middle", "zebra"])

    def test_requires_orders_dependency_before_dependent(self):
        """Module bravo requires alpha -- alpha must appear before bravo."""
        self._make_module("bravo", requires=["alpha"])
        self._make_module("alpha", requires=[])
        result = _discover_modules(self.modules_dir)
        self.assertLess(result.index("alpha"), result.index("bravo"))

    def test_requires_chain_is_fully_ordered(self):
        """alpha -> bravo -> charlie chain: alpha first, charlie last."""
        self._make_module("charlie", requires=["bravo"])
        self._make_module("bravo", requires=["alpha"])
        self._make_module("alpha", requires=[])
        result = _discover_modules(self.modules_dir)
        self.assertLess(result.index("alpha"), result.index("bravo"))
        self.assertLess(result.index("bravo"), result.index("charlie"))

    def test_missing_module_json_still_discovered(self):
        """No module.json is fine -- module is discovered with empty requires."""
        self._make_module("nomanifest")
        result = _discover_modules(self.modules_dir)
        self.assertIn("nomanifest", result)

    def test_malformed_module_json_still_discovered(self):
        """Bad JSON in module.json logs a warning but does not skip the module."""
        self._make_module("badmanifest")
        (self.modules_dir / "badmanifest" / "module.json").write_text("{not valid json")
        result = _discover_modules(self.modules_dir)
        self.assertIn("badmanifest", result)

    def test_unknown_requires_entry_is_ignored(self):
        """A requires entry for a module not in modules/ is silently skipped."""
        self._make_module("mymod", requires=["ghost"])
        result = _discover_modules(self.modules_dir)
        self.assertIn("mymod", result)

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


class TopoSortTests(SimpleTestCase):
    """Unit tests for _topo_sort() in isolation."""

    def test_empty_graph(self):
        self.assertEqual(_topo_sort({}), [])

    def test_no_deps_returns_alphabetical(self):
        self.assertEqual(_topo_sort({"b": [], "a": [], "c": []}), ["a", "b", "c"])

    def test_single_dep(self):
        result = _topo_sort({"b": ["a"], "a": []})
        self.assertLess(result.index("a"), result.index("b"))

    def test_circular_dependency_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _topo_sort({"a": ["b"], "b": ["a"]})
        self.assertIn("Circular", str(ctx.exception))

    def test_self_referential_raises(self):
        with self.assertRaises(ValueError):
            _topo_sort({"a": ["a"]})

    def test_diamond_dependency(self):
        """D requires B and C; B and C both require A -- A must be first, D last."""
        graph = {"d": ["b", "c"], "b": ["a"], "c": ["a"], "a": []}
        result = _topo_sort(graph)
        self.assertEqual(result[0], "a")
        self.assertEqual(result[-1], "d")


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
    """Integration tests -- verify module URLs are (or aren't) registered."""

    def test_health_url_always_registered(self):
        """Core health endpoint must always resolve regardless of module state."""
        url = reverse("core_app:health")
        self.assertTrue(url.startswith("/api/"))

    def test_module_url_registered_when_in_installed_module_apps(self):
        """URL discovery registers a module's prefix without importing its real deps.

        Uses a stub module on sys.modules to avoid pulling in allauth/simplejwt
        just to test the discovery mechanism.
        """
        import types
        stub = types.ModuleType("stubmod.urls")
        stub.urlpatterns = []
        sys.modules["stubmod"] = types.ModuleType("stubmod")
        sys.modules["stubmod.urls"] = stub
        try:
            with self.settings(INSTALLED_MODULE_APPS=["stubmod"]):
                from core.urls import _module_urlpatterns
                patterns = _module_urlpatterns()
                prefixes = [str(p.pattern) for p in patterns]
                self.assertIn("api/stubmod/", prefixes)
        finally:
            sys.modules.pop("stubmod", None)
            sys.modules.pop("stubmod.urls", None)

    @override_settings(INSTALLED_MODULE_APPS=[])
    def test_no_module_urls_when_list_empty(self):
        from core.urls import _module_urlpatterns
        patterns = _module_urlpatterns()
        self.assertEqual(patterns, [])
