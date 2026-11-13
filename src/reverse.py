"""Обратный граф и отдельный CLI-режим четвёртого этапа."""

__all__ = ("reverse_graph", "find_reverse_dependencies", "main")

import sys
from pathlib import Path
from typing import Optional, Sequence

from src.config import Config, load_config
from src.graph import DependencyGraph, build_dependency_graph
from src.main import CONFIG_ERROR, DEPENDENCY_ERROR, SUCCESS, create_parser
from src.npm import DependencyError
from src.repository import create_dependency_loader, load_test_repository
from src.validation import ConfigError, resolve_path


def reverse_graph(graph: DependencyGraph) -> DependencyGraph:
    """Развернуть все рёбра, сохранив также изолированные вершины."""
    reversed_edges = {name: set() for name in graph}
    for name, dependencies in graph.items():
        for dependency in dependencies:
            reversed_edges.setdefault(dependency, set()).add(name)
    return {
        name: tuple(sorted(parents))
        for name, parents in reversed_edges.items()
    }


def find_reverse_dependencies(
    graph: DependencyGraph, package: str, filter_substring: str = ""
) -> DependencyGraph:
    """Обойти входящие рёбра тем же нерекурсивным BFS третьего этапа."""
    if filter_substring and filter_substring in package:
        return {}
    if package not in graph:
        raise DependencyError(f"Пакет {package} отсутствует в графе.")
    inverted = reverse_graph(graph)
    return build_dependency_graph(
        package, inverted.__getitem__, filter_substring
    )


def _load_graph(config: Config, config_path: Path) -> DependencyGraph:
    """Взять весь тестовый репозиторий или достижимый граф npm."""
    if config.test_mode:
        path = resolve_path(config.repository, config_path.resolve().parent)
        return {
            name: tuple(dependencies)
            for name, dependencies in load_test_repository(path).items()
        }
    loader = create_dependency_loader(config, config_path)
    return build_dependency_graph(
        config.package, loader, config.filter_substring
    )


def _format_reverse(package: str, graph: DependencyGraph) -> str:
    """Показать прямые и транзитивные зависимости в порядке BFS."""
    if not graph:
        return f"Пакет {package} исключён фильтром."
    dependents = [name for name in graph if name != package]
    lines = [f"Обратные зависимости пакета {package} (BFS):"]
    lines.extend(dependents or ["(нет обратных зависимостей)"])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Запустить дополнительную операцию над известным графом."""
    parser = create_parser()
    parser.description = "Практическая работа 2, вариант 30, этап 4."
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return CONFIG_ERROR
    try:
        graph = find_reverse_dependencies(
            _load_graph(config, args.config), config.package,
            config.filter_substring,
        )
    except DependencyError as error:
        print(f"Ошибка анализа зависимостей: {error}", file=sys.stderr)
        return DEPENDENCY_ERROR
    scope = (
        "Область поиска: весь тестовый репозиторий."
        if config.test_mode else
        "Область поиска: достижимый граф npm, не весь публичный реестр."
    )
    print(scope + "\n" + _format_reverse(config.package, graph))
    return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
