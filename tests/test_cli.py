"""Интеграционные проверки настоящего процесса CLI."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.npm import DependencyError
from src.visualization import VisualizationError
from tests.helpers import run_main, write_config


PROJECT_DIR = Path(__file__).resolve().parents[1]
SUCCESS = 0
ERROR = 2
DEPENDENCY_ERROR = 1
D2_AVAILABLE = bool(
    os.environ.get("D2_BIN") or shutil.which("d2")
    or (Path.home() / ".local/bin/d2").is_file()
)


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

    def setUp(self) -> None:
        """Изолировать CLI от внешнего рендеринга в модульных тестах."""
        renderer = patch(
            "src.presentation.save_visualization",
            side_effect=lambda package, graph, output, versions: (
                output.with_suffix(".d2"), output,
            ),
        )
        renderer.start()
        self.addCleanup(renderer.stop)

    def test_success(self) -> None:
        """Построить транзитивный граф и применить фильтр из XML."""
        repository = {
            "express": {"beta": "^2.0.0", "debug": "^4.0.0"},
            "beta": {"gamma": "^1"}, "gamma": {},
        }
        with patch(
            "src.repository.fetch_direct_dependencies",
            side_effect=lambda registry, package, **kw: repository[package],
        ) as fetch:
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertTrue(stdout.endswith(
            "express\n`-- beta\n    `-- gamma\n"
        ))
        self.assertIn("SVG: ", stdout)
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
        self.assertIn("D2: ", stdout)
        self.assertIn("SVG: ", stdout)
        self.assertNotIn("|--", stdout)
        fetch.assert_not_called()

    def test_versions_from_registry(self) -> None:
        """Передать версии из HTTP-ответов в ASCII и рендеринг SVG."""
        documents = (
            {"name": "express", "version": "5.1.0",
             "dependencies": {"beta": "^1", "debug": "^4"}},
            {"name": "beta", "version": "1.2.0"},
        )
        with patch("src.npm._read_metadata", side_effect=documents) as read:
            with patch("src.presentation.save_visualization") as render:
                render.return_value = (Path("graph.d2"), Path("graph.svg"))
                code, stdout, stderr = run_main(
                    "--config", "examples/config.xml"
                )
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertTrue(stdout.endswith("express@5.1.0\n`-- beta@1.2.0\n"))
        self.assertEqual(read.call_count, len(documents))
        self.assertEqual(render.call_args.args[-1], {
            "express": "5.1.0", "beta": "1.2.0",
        })

    def test_no_dependencies(self) -> None:
        """Сообщить о пакете без зависимостей без ошибки."""
        with patch(
            "src.repository.fetch_direct_dependencies", return_value={}
        ):
            code, stdout, stderr = run_main("--config", "examples/config.xml")
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertTrue(stdout.endswith("\nexpress\n"))

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

    def test_visualization_error(self) -> None:
        """Вернуть код 1 и пустой stdout при ошибке рендеринга."""
        with patch(
            "src.repository.fetch_direct_dependencies", return_value={}
        ):
            with patch(
                "src.main.present_graph", side_effect=VisualizationError("D2")
            ):
                code, stdout, stderr = run_main(
                    "--config", "examples/config.xml"
                )
        self.assertEqual(code, DEPENDENCY_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("D2", stderr)
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
        self.assertTrue(
            stdout.endswith("Пакет express исключён фильтром.\n")
        )
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

    @unittest.skipUnless(D2_AVAILABLE, "Нужен D2 для проверки процесса CLI")
    def test_local_graph_examples(self) -> None:
        """Проверить SVG локальных примеров настоящим D2."""
        filenames = (
            "test_diamond.xml", "test_cycle.xml", "test_filter.xml",
            "test_empty.xml", "test_filtered_root.xml",
        )
        for filename in filenames:
            with self.subTest(filename=filename):
                result = run_cli("--config", f"examples/{filename}")
                self.assertEqual(result.returncode, SUCCESS, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertIn("D2: ", result.stdout)
                self.assertIn("SVG: ", result.stdout)

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

    @unittest.skipUnless(D2_AVAILABLE, "Нужен D2 для проверки run.sh")
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
        self.assertIn("SVG: ", result.stdout)
