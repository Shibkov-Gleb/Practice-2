"""Проверки ASCII, D2, SVG и ошибок внешнего рендеринга."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ascii_tree import format_ascii_tree
from src.config import load_config
from src.presentation import present_graph
from src.visualization import (
    VisualizationError,
    _find_d2,
    _render,
    format_d2,
    save_visualization,
)
from tests.helpers import write_config


SVG = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
SUCCESS = 0
FAILURE = 1
CHAIN_LENGTH = 1100


def render_stub(command: list[str], **options) -> subprocess.CompletedProcess:
    """Подменить только внешний процесс минимальным валидным SVG."""
    Path(command[-1]).write_text(SVG, encoding="utf-8")
    return subprocess.CompletedProcess(command, SUCCESS, "", "")


class AsciiTests(unittest.TestCase):
    """Проверить структуру дерева и обозначения повторных вершин."""

    def test_diamond(self) -> None:
        """Отобразить общий узел без повторного раскрытия поддерева."""
        graph = {"A": ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
        self.assertEqual(
            format_ascii_tree("A", graph),
            "A\n|-- B\n|   `-- D\n`-- C\n    `-- D [seen]",
        )

    def test_cycle(self) -> None:
        """Отметить цикл и самоссылку, не зациклившись."""
        graph = {"A": ("B", "D"), "B": ("A",), "D": ("D",)}
        self.assertEqual(
            format_ascii_tree("A", graph),
            "A\n|-- B\n|   `-- A [cycle]\n`-- D\n    `-- D [cycle]",
        )

    def test_empty_graph(self) -> None:
        """Различить исключённый корень и пакет без зависимостей."""
        self.assertEqual(format_ascii_tree("A", {"A": ()}), "A")
        self.assertEqual(
            format_ascii_tree("A", {}), "Пакет A исключён фильтром."
        )

    def test_deep_chain(self) -> None:
        """Обойти дерево без рекурсии, сохранив все уровни."""
        graph = {str(index): (str(index + 1),)
                 for index in range(CHAIN_LENGTH)}
        graph[str(CHAIN_LENGTH)] = ()
        lines = format_ascii_tree("0", graph).splitlines()
        self.assertEqual(len(lines), CHAIN_LENGTH + 1)
        self.assertTrue(lines[-1].endswith(f"`-- {CHAIN_LENGTH}"))


class VisualizationTests(unittest.TestCase):
    """Проверить файлы и ошибки, изолируя внешний процесс D2."""

    def setUp(self) -> None:
        """Создать отдельный каталог и подменить бинарный компилятор."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.output = self.directory / "graph.svg"
        environment = patch.dict(os.environ, {"D2_BIN": "/fake/d2"})
        environment.start()
        self.addCleanup(environment.stop)
        self.renderer = patch(
            "src.visualization.subprocess.run", side_effect=render_stub
        )
        self.run = self.renderer.start()
        self.addCleanup(self.renderer.stop)

    def test_d2_nodes_edges_cycles_and_scoped_names(self) -> None:
        """Применить безопасные идентификаторы и quoted labels D2."""
        self.assertEqual(
            format_d2("@types/node", {
                "@types/node": ("B",), "B": ("B", "@types/node"),
            }),
            'direction: right\nn0: "@types/node"\nn1: "B"\n'
            'n0 -> n1\nn1 -> n1\nn1 -> n0\n',
        )

    def test_d2_empty_and_isolated(self) -> None:
        """Сформировать содержательную диаграмму даже без рёбер."""
        self.assertIn('n0: "A"', format_d2("A", {"A": ()}))
        self.assertIn("excluded by filter", format_d2("A", {}))

    def test_save_both_files(self) -> None:
        """Сохранить текст и SVG только после успешной компиляции."""
        source, image = save_visualization("A", {"A": ()}, self.output)
        self.assertEqual(image.read_text(encoding="utf-8"), SVG)
        self.assertIn('n0: "A"', source.read_text(encoding="utf-8"))
        command = self.run.call_args.args[0]
        self.assertEqual(command[:2], ["/fake/d2", "--layout=dagre"])
        self.assertNotIn("shell", self.run.call_args.kwargs)
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()),
                         ["graph.d2", "graph.svg"])

    def test_failure_keeps_old_results(self) -> None:
        """Сохранить старые файлы и удалить временные при ошибке D2."""
        self.output.write_text("old SVG", encoding="utf-8")
        source = self.output.with_suffix(".d2")
        source.write_text("old D2", encoding="utf-8")
        self.run.side_effect = None
        self.run.return_value = subprocess.CompletedProcess(
            [], FAILURE, "", "invalid D2"
        )
        with self.assertRaisesRegex(VisualizationError, "invalid D2"):
            save_visualization("A", {"A": ()}, self.output)
        self.assertEqual(self.output.read_text(), "old SVG")
        self.assertEqual(source.read_text(), "old D2")
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()),
                         ["graph.d2", "graph.svg"])

    def test_invalid_missing_or_non_svg_result(self) -> None:
        """Отклонить отсутствие SVG, битый XML и чужой корневой тег."""
        self.run.side_effect = None
        self.run.return_value = subprocess.CompletedProcess(
            [], SUCCESS, "", ""
        )
        with self.assertRaises(VisualizationError):
            save_visualization("A", {"A": ()}, self.output)
        for document in ("<svg", "<html/>"):
            with self.subTest(document=document):
                with tempfile.TemporaryDirectory() as directory:
                    image = Path(directory) / "bad.svg"
                    image.write_text(document, encoding="utf-8")
                    with self.assertRaises(VisualizationError):
                        _render(Path("input.d2"), image)

    def test_process_and_filesystem_errors(self) -> None:
        """Обработать отсутствие D2, timeout и отказ записи."""
        for error in (
            FileNotFoundError("d2"), PermissionError("denied"),
            subprocess.TimeoutExpired("d2", 60),
        ):
            with self.subTest(error=error):
                self.run.side_effect = error
                with self.assertRaises(VisualizationError):
                    save_visualization("A", {"A": ()}, self.output)
                self.assertFalse(self.output.exists())

    def test_source_is_directory(self) -> None:
        """Отклонить каталог на месте D2 до запуска процесса."""
        self.output.with_suffix(".d2").mkdir()
        with self.assertRaises(VisualizationError):
            save_visualization("A", {"A": ()}, self.output)
        self.run.assert_not_called()

    def test_missing_compiler(self) -> None:
        """Сообщить инструкцию при отсутствии компилятора D2."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.visualization.shutil.which", return_value=None):
                with patch("pathlib.Path.is_file", return_value=False):
                    with self.assertRaisesRegex(VisualizationError, "D2_BIN"):
                        _find_d2()

    def test_compiler_from_path(self) -> None:
        """Использовать установленный в PATH компилятор без D2_BIN."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.visualization.shutil.which", return_value="d2"):
                self.assertEqual(_find_d2(), "d2")

    def test_ascii_setting(self) -> None:
        """Выводить дерево только при включённом параметре XML."""
        for enabled in ("true", "false"):
            with self.subTest(enabled=enabled):
                path = write_config(self.directory, ascii_tree=enabled)
                output = present_graph(
                    load_config(path), path, {"express": ("B",), "B": ()}
                )
                self.assertEqual("`-- B" in output, enabled == "true")
                self.assertTrue(self.output.exists())

    def test_protect_repository_and_config(self) -> None:
        """Защитить входы, включая репозиторий с расширением .d2."""
        repository = self.directory / "graph.d2"
        repository.write_text('{"A": []}', encoding="utf-8")
        path = write_config(
            self.directory, repository="graph.d2", test_mode="true"
        )
        config = load_config(path)
        with self.assertRaises(VisualizationError):
            present_graph(config, path, {"A": ()})
        with self.assertRaises(VisualizationError):
            present_graph(config, self.output, {"A": ()})
        self.assertEqual(repository.read_text(), '{"A": []}')
        self.run.assert_not_called()
