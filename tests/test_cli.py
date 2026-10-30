"""Интеграционные проверки настоящего процесса CLI."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.npm import DependencyError
from tests.helpers import run_main, write_config


PROJECT_DIR = Path(__file__).resolve().parents[1]
SUCCESS = 0
ERROR = 2
DEPENDENCY_ERROR = 1


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
        """Вывести прямые зависимости, сохранив настройки реестра."""
        dependencies = {"beta": "^2.0.0", "debug": "^4.0.0"}
        with patch(
            "src.main.fetch_direct_dependencies", return_value=dependencies
        ) as fetch:
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout,
            "Прямые зависимости пакета express:\n"
            "beta: ^2.0.0\ndebug: ^4.0.0\n",
        )
        fetch.assert_called_once_with("https://registry.npmjs.org", "express")

    def test_test_example(self) -> None:
        """Сообщить, что тестовый граф относится к этапу 3."""
        with patch("src.main.fetch_direct_dependencies") as fetch:
            code, stdout, stderr = run_main(
                "--config", "examples/test_config.xml"
            )
        self.assertEqual(code, DEPENDENCY_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("test_mode", stderr)
        self.assertIn("этапу 3", stderr)
        fetch.assert_not_called()

    def test_no_dependencies(self) -> None:
        """Сообщить о пакете без зависимостей без ошибки."""
        with patch("src.main.fetch_direct_dependencies", return_value={}):
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "У пакета express нет прямых зависимостей.\n")

    def test_dependency_error(self) -> None:
        """Направить ошибку получения данных в stderr без traceback."""
        with patch(
            "src.main.fetch_direct_dependencies",
            side_effect=DependencyError("Реестр недоступен."),
        ):
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, DEPENDENCY_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("Реестр недоступен", stderr)
        self.assertNotIn("Traceback", stderr)

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
                    "--help",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, SUCCESS, result.stderr)
        self.assertIn("--config", result.stdout)
