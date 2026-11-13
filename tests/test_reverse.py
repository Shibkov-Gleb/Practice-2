"""Проверки обратных зависимостей четвёртого этапа."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.npm import DependencyError
from src.reverse import find_reverse_dependencies, main, reverse_graph
from tests.helpers import write_config


SUCCESS = 0
CONFIG_ERROR = 2
DEPENDENCY_ERROR = 1
CHAIN_LENGTH = 1500


class ReverseTests(unittest.TestCase):
    """Проверить инверсию рёбер и BFS без потери зависимых пакетов."""

    def test_invert_isolated_and_duplicate_edges(self) -> None:
        """Сохранить изолированные узлы и убрать дубли рёбер."""
        self.assertEqual(
            reverse_graph({"A": ("B", "B"), "B": (), "C": ()}),
            {"A": (), "B": ("A",), "C": ()},
        )

    def test_full_repository_and_bfs_order(self) -> None:
        """Найти зависимые узлы вне прямого графа выбранного пакета."""
        graph = {"A": ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
        result = find_reverse_dependencies(graph, "D")
        self.assertEqual(list(result), ["D", "B", "C", "A"])
        self.assertEqual(result["D"], ("B", "C"))

    def test_cycle_and_self_reference(self) -> None:
        """Завершить обход цикла, сохранив обратные рёбра."""
        graph = {"A": ("B",), "B": ("C",), "C": ("A", "C")}
        self.assertEqual(
            find_reverse_dependencies(graph, "C"),
            {"C": ("B", "C"), "B": ("A",), "A": ("C",)},
        )

    def test_filter(self) -> None:
        """Не проходить через исключённого зависимого родителя."""
        graph = {"A": ("B",), "B": ("C",), "C": ()}
        self.assertEqual(
            find_reverse_dependencies(graph, "C", "B"), {"C": ()}
        )
        self.assertEqual(find_reverse_dependencies(graph, "C", "C"), {})

    def test_unknown_package(self) -> None:
        """Сообщить об отсутствии пакета в репозитории."""
        with self.assertRaises(DependencyError):
            find_reverse_dependencies({"A": ()}, "B")

    def test_deep_chain(self) -> None:
        """Обойти цепочку длиннее обычного предела рекурсии Python."""
        graph = {str(index): (str(index + 1),)
                 for index in range(CHAIN_LENGTH)}
        graph[str(CHAIN_LENGTH)] = ()
        result = find_reverse_dependencies(graph, str(CHAIN_LENGTH))
        self.assertEqual(len(result), CHAIN_LENGTH + 1)

    def test_cli_full_repository(self) -> None:
        """Проверить локальный CLI и отсутствие запросов к npm."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "repo.json").write_text(
                json.dumps({"A": ["B"], "B": [], "C": ["A"]}),
                encoding="utf-8",
            )
            config = write_config(
                base, package="B", repository="repo.json", test_mode="true"
            )
            with patch("src.repository.fetch_direct_dependencies") as fetch:
                code, stdout, stderr = capture_reverse(config)
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertIn("B (BFS):\nA\nC\n", stdout)
        fetch.assert_not_called()

    def test_cli_cycle_does_not_list_self(self) -> None:
        """Не выдавать исходный пакет за собственную зависимость."""
        code, stdout, stderr = capture_reverse(
            Path("examples/test_cycle.xml")
        )
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertTrue(stdout.endswith("BFS):\nC\nB\n"))

    def test_cli_configuration_error(self) -> None:
        """Сохранить отдельный код ошибки конфигурации."""
        code, stdout, stderr = capture_reverse(Path("missing.xml"))
        self.assertEqual(code, CONFIG_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("Ошибка конфигурации", stderr)

    def test_cli_repository_error(self) -> None:
        """Не печатать результат при ошибке исходных данных."""
        with patch("src.reverse._load_graph", side_effect=DependencyError()):
            code, stdout, stderr = capture_reverse(
                Path("examples/test_config.xml")
            )
        self.assertEqual(code, DEPENDENCY_ERROR)
        self.assertEqual(stdout, "")
        self.assertIn("Ошибка анализа", stderr)

    def test_cli_filtered_remote_root(self) -> None:
        """Не запрашивать npm для исключённого корня."""
        with tempfile.TemporaryDirectory() as directory:
            config = write_config(Path(directory), filter_substring="press")
            with patch("src.repository.fetch_direct_dependencies") as fetch:
                code, stdout, stderr = capture_reverse(config)
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertIn("исключён фильтром", stdout)
        fetch.assert_not_called()

    def test_cli_remote_scope(self) -> None:
        """Явно ограничить вывод известным графом, а не всем npm."""
        with patch(
            "src.repository.fetch_direct_dependencies", return_value={}
        ):
            code, stdout, stderr = capture_reverse(
                Path("examples/no_dependencies.xml")
            )
        self.assertEqual(code, SUCCESS)
        self.assertEqual(stderr, "")
        self.assertIn("не весь публичный реестр", stdout)
        self.assertIn("нет обратных зависимостей", stdout)


def capture_reverse(config: Path) -> tuple[int, str, str]:
    """Запустить режим четвёртого этапа с перехватом вывода."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(["--config", str(config)])
    return code, stdout.getvalue(), stderr.getvalue()
