"""Нерекурсивное ASCII-представление графа зависимостей."""

__all__ = ("format_ascii_tree",)

from typing import Mapping, Optional

from src.graph import DependencyGraph, format_package


def format_ascii_tree(
    package: str, graph: DependencyGraph,
    versions: Optional[Mapping[str, str]] = None,
) -> str:
    """Показать цикл и общий узел, не раскрывая их повторно."""
    if not graph:
        return f"Пакет {package} исключён фильтром."
    lines = [format_package(package, versions)]
    expanded = {package}
    stack = []
    _push_children(stack, graph, package, "", frozenset({package}))
    while stack:
        name, prefix, last, ancestors = stack.pop()
        marker = "`-- " if last else "|-- "
        suffix = _reference_suffix(name, ancestors, expanded)
        lines.append(prefix + marker + format_package(name, versions) + suffix)
        if suffix:
            continue
        expanded.add(name)
        continuation = "    " if last else "|   "
        _push_children(
            stack, graph, name, prefix + continuation, ancestors | {name}
        )
    return "\n".join(lines)


def _push_children(
    stack: list, graph: DependencyGraph, name: str,
    prefix: str, ancestors: frozenset[str],
) -> None:
    """Положить детей на стек в обратном порядке для прямого вывода."""
    dependencies = graph[name]
    final_index = len(dependencies) - 1
    for index in reversed(range(len(dependencies))):
        stack.append(
            (dependencies[index], prefix, index == final_index, ancestors)
        )


def _reference_suffix(
    name: str, ancestors: frozenset[str], expanded: set[str]
) -> str:
    """Отличить замыкание текущего пути от общей зависимости."""
    if name in ancestors:
        return " [cycle]"
    if name in expanded:
        return " [seen]"
    return ""
