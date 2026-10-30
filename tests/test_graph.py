"""Проверки обхода BFS, фильтрации, циклов и глубокой цепочки."""

import unittest
from unittest.mock import Mock, call

from src.graph import build_dependency_graph, format_graph
from src.npm import DependencyError


CHAIN_LENGTH = 1500


class GraphTests(unittest.TestCase):
    """Проверить независимый от источника данных алгоритм BFS."""

    def test_breadth_first_order(self) -> None:
        """Обходить уровень целиком до перехода к следующему уровню."""
        repository = {
            "A": ["C", "B"], "B": ["D"], "C": ["E"],
            "D": ["F"], "E": [], "F": [],
        }
        loader = Mock(side_effect=repository.__getitem__)
        graph = build_dependency_graph("A", loader)
        self.assertEqual(list(graph), ["A", "B", "C", "D", "E", "F"])
        self.assertEqual(graph["A"], ("B", "C"))
        self.assertEqual(
            loader.call_args_list,
            [call(name) for name in ("A", "B", "C", "D", "E", "F")],
        )

    def test_shared_dependency_and_duplicates(self) -> None:
        """Загрузить общий пакет один раз, сохранив входящие рёбра."""
        repository = {
            "A": ["B", "B", "C"], "B": ["D"], "C": ["D"], "D": []
        }
        loader = Mock(side_effect=repository.__getitem__)
        graph = build_dependency_graph("A", loader)
        self.assertEqual(graph, {
            "A": ("B", "C"), "B": ("D",), "C": ("D",), "D": (),
        })
        self.assertEqual(loader.call_args_list, [
            call("A"), call("B"), call("C"), call("D"),
        ])

    def test_cycle(self) -> None:
        """Сохранить ребро цикла без повторной загрузки узла."""
        repository = {"A": ["B"], "B": ["C"], "C": ["A"]}
        loader = Mock(side_effect=repository.__getitem__)
        graph = build_dependency_graph("A", loader)
        self.assertEqual(graph, {"A": ("B",), "B": ("C",), "C": ("A",)})
        self.assertEqual(
            loader.call_args_list, [call("A"), call("B"), call("C")]
        )

    def test_self_reference(self) -> None:
        """Пакет, зависящий от себя, должен загружаться один раз."""
        loader = Mock(return_value=["A"])
        self.assertEqual(build_dependency_graph("A", loader), {"A": ("A",)})
        loader.assert_called_once_with("A")

    def test_filtered_branch(self) -> None:
        """Исключить пакет и недостижимую без него ветвь графа."""
        repository = {"A": ["B", "C"], "B": ["D"], "C": [], "D": []}
        loader = Mock(side_effect=repository.__getitem__)
        graph = build_dependency_graph("A", loader, "B")
        self.assertEqual(graph, {"A": ("C",), "C": ()})
        self.assertEqual(loader.call_args_list, [call("A"), call("C")])

    def test_filtered_shared_dependency(self) -> None:
        """Сохранить узел, достижимый по оставшемуся пути."""
        repository = {
            "A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []
        }
        graph = build_dependency_graph("A", repository.__getitem__, "B")
        self.assertEqual(graph, {"A": ("C",), "C": ("D",), "D": ()})

    def test_empty_filter(self) -> None:
        """Пустой фильтр не исключает ни один пакет."""
        repository = {"A": ["B"], "B": []}
        self.assertEqual(
            build_dependency_graph("A", repository.__getitem__, ""),
            {"A": ("B",), "B": ()},
        )

    def test_case_sensitive_substring(self) -> None:
        """Сопоставлять подстроку внутри имени с учётом регистра."""
        repository = {"ROOT": ["abc", "xabcx", "ABC"], "ABC": []}
        graph = build_dependency_graph("ROOT", repository.__getitem__, "abc")
        self.assertEqual(graph, {"ROOT": ("ABC",), "ABC": ()})

    def test_filtered_root(self) -> None:
        """Не загружать исходный пакет, если он подходит под фильтр."""
        loader = Mock()
        self.assertEqual(build_dependency_graph("ROOT", loader, "OO"), {})
        loader.assert_not_called()

    def test_unreachable_nodes(self) -> None:
        """Не включать несвязанные с исходным пакетом компоненты."""
        repository = {"A": [], "B": ["C"], "C": []}
        self.assertEqual(
            build_dependency_graph("A", repository.__getitem__), {"A": ()}
        )

    def test_deep_chain_without_recursion(self) -> None:
        """Обработать цепочку длиннее стандартного стека рекурсии."""
        last_index = CHAIN_LENGTH - 1
        repository = {
            f"N{index}": [f"N{index + 1}"] for index in range(last_index)
        }
        repository[f"N{last_index}"] = []
        graph = build_dependency_graph("N0", repository.__getitem__)
        self.assertEqual(len(graph), CHAIN_LENGTH)
        self.assertEqual(graph[f"N{last_index}"], ())

    def test_loader_error(self) -> None:
        """Передать ошибку источника данных вызывающему коду."""
        loader = Mock(side_effect=DependencyError("unavailable"))
        with self.assertRaisesRegex(DependencyError, "unavailable"):
            build_dependency_graph("A", loader)

    def test_format_graph(self) -> None:
        """Показать узлы и рёбра в порядке BFS, включая листья."""
        graph = {"A": ("B", "C"), "B": (), "C": ("A",)}
        self.assertEqual(
            format_graph("A", graph),
            "Граф зависимостей пакета A (BFS):\n"
            "A -> B, C\nB -> (нет зависимостей)\nC -> A",
        )
        self.assertEqual(format_graph("A", {}), "Пакет A исключён фильтром.")
