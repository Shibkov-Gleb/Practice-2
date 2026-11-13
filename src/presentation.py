"""Вывод результатов пятого этапа и защита входных файлов."""

__all__ = ("present_graph",)

from pathlib import Path

from src.ascii_tree import format_ascii_tree
from src.config import Config
from src.graph import DependencyGraph
from src.validation import resolve_path
from src.visualization import VisualizationError, save_visualization


def present_graph(
    config: Config, config_path: Path, graph: DependencyGraph
) -> str:
    """Сохранить граф и при необходимости добавить ASCII-дерево."""
    output = resolve_path(config.output_file, config_path.resolve().parent)
    _protect_inputs(config, config_path, output)
    source, image = save_visualization(config.package, graph, output)
    lines = [f"D2: {source}", f"SVG: {image}"]
    if config.ascii_tree:
        lines.append(format_ascii_tree(config.package, graph))
    return "\n".join(lines)


def _protect_inputs(config: Config, config_path: Path, output: Path) -> None:
    """Защитить XML и локальный репозиторий от перезаписи."""
    inputs = {config_path.resolve()}
    if config.test_mode:
        inputs.add(
            resolve_path(config.repository, config_path.resolve().parent)
        )
    if inputs.intersection({output, output.with_suffix(".d2")}):
        raise VisualizationError("Пути D2/SVG совпадают с входным файлом.")
