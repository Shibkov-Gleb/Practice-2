"""Итеративное построение графа зависимостей обходом в ширину."""

__all__ = (
    "DependencyGraph",
    "DependencyLoader",
    "build_dependency_graph",
    "format_graph",
)

from collections import deque
from typing import Callable, Iterable


DependencyGraph = dict[str, tuple[str, ...]]
DependencyLoader = Callable[[str], Iterable[str]]


def build_dependency_graph(
    package: str,
    load_dependencies: DependencyLoader,
    filter_substring: str = "",
) -> DependencyGraph:
    """Построить достижимый граф BFS, сохранив рёбра циклов."""
    if _is_excluded(package, filter_substring):
        return {}
    graph = {}
    queue = deque([package])
    discovered = {package}
    while queue:
        current = queue.popleft()
        dependencies = _filter_dependencies(
            load_dependencies(current), filter_substring
        )
        graph[current] = dependencies
        for dependency in dependencies:
            if dependency not in discovered:
                discovered.add(dependency)
                queue.append(dependency)
    return graph


def _filter_dependencies(
    dependencies: Iterable[str], filter_substring: str
) -> tuple[str, ...]:
    """Отсортировать уникальные имена после фильтрации."""
    return tuple(sorted({
        name for name in dependencies
        if not _is_excluded(name, filter_substring)
    }))


def _is_excluded(package: str, filter_substring: str) -> bool:
    """Проверить непустую подстроку с учётом регистра."""
    return bool(filter_substring) and filter_substring in package


def format_graph(package: str, graph: DependencyGraph) -> str:
    """Представить граф списками смежности в порядке обхода BFS."""
    if not graph:
        return f"Пакет {package} исключён фильтром."
    lines = [f"Граф зависимостей пакета {package} (BFS):"]
    for name, dependencies in graph.items():
        targets = ", ".join(dependencies) or "(нет зависимостей)"
        lines.append(f"{name} -> {targets}")
    return "\n".join(lines)
