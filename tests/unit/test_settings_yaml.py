import tempfile
import unittest
from pathlib import Path

from app.settings import load_simple_yaml


class TestSettingsYaml(unittest.TestCase):
    def test_load_yaml_coerces_numeric_and_boolean_values(self) -> None:
        content = "\n".join(
            [
                "app:",
                "  name: local-audiobook",
                "server:",
                "  port: 8080",
                "  timeout: 30",
                "  ratio: 0.5",
                "  enabled: true",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "test_config.yaml"
            config_path.write_text(content, encoding="utf-8")

            data = load_simple_yaml(config_path)

            self.assertEqual(data["app"]["name"], "local-audiobook")
            self.assertEqual(data["server"]["port"], 8080)
            self.assertEqual(data["server"]["timeout"], 30)
            self.assertEqual(data["server"]["ratio"], 0.5)
            self.assertTrue(data["server"]["enabled"])

