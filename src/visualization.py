"""Текст D2 и преобразование диаграммы в SVG внешним компилятором."""

__all__ = ("VisualizationError", "format_d2", "save_visualization")

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Mapping, Optional
from xml.etree import ElementTree

from src.graph import DependencyGraph, format_package


RENDER_TIMEOUT = 60
SUCCESS = 0
SVG_TAG = "{http://www.w3.org/2000/svg}svg"


class VisualizationError(ValueError):
    """Ошибка формирования или сохранения изображения."""


def format_d2(
    package: str, graph: DependencyGraph,
    versions: Optional[Mapping[str, str]] = None,
) -> str:
    """Описать все вершины и рёбра, включая циклы, на языке D2."""
    lines = ["direction: right"]
    identifiers = {name: f"n{index}" for index, name in enumerate(graph)}
    if not graph:
        label = json.dumps(f"{package}: excluded by filter", ensure_ascii=True)
        return "\n".join([*lines, f"empty: {label}", ""])
    for name, identifier in identifiers.items():
        label = json.dumps(format_package(name, versions), ensure_ascii=True)
        lines.append(f"{identifier}: {label}")
    for name, dependencies in graph.items():
        for dependency in dependencies:
            lines.append(f"{identifiers[name]} -> {identifiers[dependency]}")
    return "\n".join([*lines, ""])


def _find_d2() -> str:
    """Найти D2_BIN, d2 в PATH или стандартном ~/.local/bin."""
    executable = os.environ.get("D2_BIN") or shutil.which("d2")
    if executable:
        return executable
    local = Path.home() / ".local" / "bin" / "d2"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    raise VisualizationError(
        "Компилятор D2 не найден. Установите d2 или задайте D2_BIN."
    )


def _render(source: Path, image: Path) -> None:
    """Запустить D2 без shell и проверить код возврата и корень SVG."""
    result = subprocess.run(
        [_find_d2(), "--layout=dagre", str(source), str(image)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=RENDER_TIMEOUT, check=False,
    )
    if result.returncode != SUCCESS:
        details = result.stderr.strip() or result.stdout.strip()
        raise VisualizationError(f"D2 завершился с ошибкой: {details}")
    try:
        root = ElementTree.parse(image).getroot()
    except (OSError, ElementTree.ParseError) as error:
        raise VisualizationError("D2 не создал корректный SVG.") from error
    if root.tag != SVG_TAG:
        raise VisualizationError("Результат D2 не является SVG.")


def save_visualization(
    package: str, graph: DependencyGraph, output: Path,
    versions: Optional[Mapping[str, str]] = None,
) -> tuple[Path, Path]:
    """Сохранить D2 и SVG после успешного временного рендеринга."""
    output = output.resolve()
    source = output.with_suffix(".d2")
    try:
        if source.exists() and not source.is_file():
            raise VisualizationError(f"Путь D2 не является файлом: {source}")
        with tempfile.TemporaryDirectory(
            prefix=".practice2-", dir=output.parent
        ) as directory:
            staged_source = Path(directory) / "graph.d2"
            staged_image = Path(directory) / "graph.svg"
            staged_source.write_text(
                format_d2(package, graph, versions), encoding="utf-8"
            )
            _render(staged_source, staged_image)
            staged_source.replace(source)
            staged_image.replace(output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if isinstance(error, VisualizationError):
            raise
        message = f"Не удалось сохранить граф: {error}"
        raise VisualizationError(message) from error
    return source, output
