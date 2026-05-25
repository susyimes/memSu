from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def load_provider_module():
    path = Path("hermes/plugins/memory/memsu/__init__.py")
    spec = importlib.util.spec_from_file_location("memsu_provider_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ProviderTests(unittest.TestCase):
    def test_provider_exposes_expected_tools(self) -> None:
        module = load_provider_module()
        provider = module.MemSuMemoryProvider()

        tool_names = {schema["name"] for schema in provider.get_tool_schemas()}

        self.assertIn("memsu_recall", tool_names)
        self.assertIn("memsu_policy_check", tool_names)
        self.assertIn("memsu_curator_run", tool_names)

    def test_provider_prefetch_returns_empty_when_service_unavailable(self) -> None:
        module = load_provider_module()
        provider = module.MemSuMemoryProvider()
        provider.initialize("test-session")

        self.assertEqual("", provider.prefetch("anything useful"))


if __name__ == "__main__":
    unittest.main()

