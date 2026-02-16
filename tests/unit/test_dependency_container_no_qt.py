import importlib
import subprocess
import sys
import unittest


class TestDependencyContainerImport(unittest.TestCase):
    def test_dependency_container_imports_without_qt_runtime(self) -> None:
        """Verify dependency_container can be imported without loading PyQt5.
        
        This test runs in a subprocess to ensure PyQt5 hasn't been loaded by other tests.
        """
        # If PyQt5 is already loaded (by other tests), run in subprocess for isolation
        if "PyQt5" in sys.modules:
            result = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, 'src'); "
                 "import app.dependency_container; "
                 "assert 'PyQt5' not in sys.modules, 'PyQt5 should not be loaded'"],
                capture_output=True,
                text=True,
                cwd="/home/thibault/work/local-audiobook"
            )
            self.assertEqual(result.returncode, 0,
                           f"Subprocess test failed: {result.stderr}")
        else:
            # PyQt5 not loaded yet, test directly
            module = importlib.import_module("app.dependency_container")
            self.assertIsNotNone(module)
            self.assertNotIn("PyQt5", sys.modules)
