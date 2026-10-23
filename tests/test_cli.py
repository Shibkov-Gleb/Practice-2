"""Интеграционные проверки настоящего процесса CLI."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import write_config


PROJECT_DIR = Path(__file__).resolve().parents[1]
SUCCESS = 0
ERROR = 2


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    """Запустить приложение тем же интерпретатором, что и тесты."""
    return subprocess.run(
        [sys.executable, "-B", "-m", "src.main", *arguments],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


class CliTests(unittest.TestCase):
    """Проверить stdout, stderr и коды завершения приложения."""

    def test_success(self) -> None:
        """Вывести ровно шесть строк и ничего в stderr."""
        result = run_cli("--config", "examples/config.xml")
        self.assertEqual(result.returncode, SUCCESS)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "package=express\n"
            "repository=https://registry.npmjs.org\n"
            "test_mode=false\n"
            "output_file=graph.svg\n"
            "ascii_tree=true\n"
            "filter_substring=debug\n",
        )

    def test_test_example(self) -> None:
        """Загрузить пример локального репозитория с пустым фильтром."""
        result = run_cli("--config", "examples/test_config.xml")
        self.assertEqual(result.returncode, SUCCESS)
        self.assertIn("package=A\n", result.stdout)
        self.assertIn("test_mode=true\n", result.stdout)
        self.assertTrue(result.stdout.endswith("filter_substring=\n"))

    def test_help(self) -> None:
        """Справка должна быть доступна без XML-файла."""
        result = run_cli("--help")
        self.assertEqual(result.returncode, SUCCESS)
        self.assertIn("--config", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_argument_errors(self) -> None:
        """Обработать ошибки аргументов командной строки."""
        for arguments in ((), ("--config",), ("--unknown",)):
            with self.subTest(arguments=arguments):
                result = run_cli(*arguments)
                self.assertEqual(result.returncode, ERROR)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_config_errors(self) -> None:
        """Ошибка XML-файла должна попасть только в stderr."""
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "missing.xml")
            result = run_cli("--config", path)
        self.assertEqual(result.returncode, ERROR)
        self.assertEqual(result.stdout, "")
        self.assertIn("Ошибка конфигурации", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_each_parameter_error(self) -> None:
        """Проверить через CLI ошибку каждого параметра."""
        invalid_values = {
            "package": "bad name",
            "repository": "invalid",
            "test_mode": "yes",
            "output_file": "graph.png",
            "ascii_tree": "no",
            "filter_substring": "first\nsecond",
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, value in invalid_values.items():
                with self.subTest(name=name):
                    path = write_config(Path(directory), **{name: value})
                    result = run_cli("--config", str(path))
                    self.assertEqual(result.returncode, ERROR)
                    self.assertEqual(result.stdout, "")
                    self.assertIn(name, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_launcher_from_another_directory(self) -> None:
        """Скрипт запуска работает вне корневого каталога проекта."""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "sh",
                    str(PROJECT_DIR / "run.sh"),
                    "--config",
                    str(PROJECT_DIR / "examples/test_config.xml"),
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, SUCCESS, result.stderr)
        self.assertIn("test_mode=true", result.stdout)
