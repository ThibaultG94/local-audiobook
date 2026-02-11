import importlib
import sys
import unittest


class TestDependencyContainerImport(unittest.TestCase):
    def test_dependency_container_imports_without_qt_runtime(self) -> None:
        module = importlib.import_module("app.dependency_container")
        self.assertIsNotNone(module)
        self.assertNotIn("PyQt5", sys.modules)
