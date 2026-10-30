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
        """Построить транзитивный граф и применить фильтр из XML."""
        repository = {
            "express": {"beta": "^2.0.0", "debug": "^4.0.0"},
            "beta": {"gamma": "^1"}, "gamma": {},
        }
        with patch(
            "src.repository.fetch_direct_dependencies",
            side_effect=lambda registry, package: repository[package],
        ) as fetch:
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout,
            "Граф зависимостей пакета express (BFS):\n"
            "express -> beta\nbeta -> gamma\ngamma -> (нет зависимостей)\n",
        )
        self.assertEqual(
            [item.args for item in fetch.call_args_list],
            [("https://registry.npmjs.org", package)
             for package in ("express", "beta", "gamma")],
        )

    def test_test_example(self) -> None:
        """Прочитать локальный граф и не обращаться к npm."""
        with patch("src.repository.fetch_direct_dependencies") as fetch:
            code, stdout, stderr = run_main(
                "--config", "examples/test_config.xml"
            )
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout, "Граф зависимостей пакета A (BFS):\n"
            "A -> B, C\nB -> (нет зависимостей)\nC -> (нет зависимостей)\n",
        )
        fetch.assert_not_called()

    def test_no_dependencies(self) -> None:
        """Сообщить о пакете без зависимостей без ошибки."""
        with patch(
            "src.repository.fetch_direct_dependencies", return_value={}
        ):
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout, "Граф зависимостей пакета express (BFS):\n"
            "express -> (нет зависимостей)\n",
        )

    def test_dependency_error(self) -> None:
        """Направить ошибку получения данных в stderr без traceback."""
        with patch(
            "src.repository.fetch_direct_dependencies",
            side_effect=DependencyError("Реестр недоступен."),
        ):
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, DEPENDENCY_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("Реестр недоступен", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_transitive_error_without_partial_output(self) -> None:
        """Не печатать частичный граф при ошибке транзитивного узла."""
        with patch(
            "src.repository.fetch_direct_dependencies",
            side_effect=[{"beta": "*"}, DependencyError("beta unavailable")],
        ):
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, DEPENDENCY_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("beta unavailable", stderr)

    def test_filtered_root_without_network(self) -> None:
        """Не запрашивать метаданные исключённого исходного пакета."""
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(Path(directory), filter_substring="press")
            with patch("src.repository.fetch_direct_dependencies") as fetch:
                code, stdout, stderr = run_main("--config", str(path))
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "Пакет express исключён фильтром.\n")
        fetch.assert_not_called()

    def test_invalid_local_graph(self) -> None:
        """Обработать ошибки тестового графа без traceback."""
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository.json"
            path = write_config(
                Path(directory), package="A", test_mode="true",
                repository=repository.name, filter_substring="",
            )
            for document in ("{", "{}", '{"A": ["B"]}'):
                with self.subTest(document=document):
                    repository.write_text(document, encoding="utf-8")
                    result = run_cli("--config", str(path))
                    self.assertEqual(result.returncode, DEPENDENCY_ERROR)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("Ошибка анализа", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_local_graph_examples(self) -> None:
        """Проверить демонстрационные графы через CLI."""
        expected_bodies = {
            "test_diamond.xml": "A -> B, C\nB -> D\nC -> D\n"
            "D -> (нет зависимостей)\n",
            "test_cycle.xml": "A -> B, D\nB -> C\nD -> D\nC -> A\n",
            "test_filter.xml": "A -> C\nC -> D\nD -> (нет зависимостей)\n",
            "test_empty.xml": "A -> (нет зависимостей)\n",
        }
        for filename, body in expected_bodies.items():
            with self.subTest(filename=filename):
                result = run_cli("--config", f"examples/{filename}")
                self.assertEqual(result.returncode, SUCCESS, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(
                    result.stdout, "Граф зависимостей пакета A (BFS):\n" + body
                )
        result = run_cli("--config", "examples/test_filtered_root.xml")
        self.assertEqual(result.returncode, SUCCESS)
        self.assertEqual(result.stdout, "Пакет A исключён фильтром.\n")

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
        self.assertIn("A -> B, C", result.stdout)
