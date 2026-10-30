"""Точка входа CLI: чтение XML и построение графа зависимостей BFS."""

__all__ = (
    "SUCCESS", "CONFIG_ERROR", "DEPENDENCY_ERROR", "create_parser", "main",
)

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.config import load_config
from src.graph import build_dependency_graph, format_graph
from src.npm import DependencyError
from src.repository import create_dependency_loader
from src.validation import ConfigError


SUCCESS = 0
CONFIG_ERROR = 2
DEPENDENCY_ERROR = 1


def create_parser() -> argparse.ArgumentParser:
    """Создать CLI с опцией выбора XML-конфигурации."""
    parser = argparse.ArgumentParser(
        description="Практическая работа 2, вариант 30, этап 3."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        metavar="FILE",
        help="путь к XML-файлу со всеми шестью настройками",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Построить граф по настройкам и вернуть код результата."""
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return CONFIG_ERROR
    try:
        loader = create_dependency_loader(config, args.config)
        graph = build_dependency_graph(
            config.package, loader, config.filter_substring
        )
    except DependencyError as error:
        print(f"Ошибка анализа зависимостей: {error}", file=sys.stderr)
        return DEPENDENCY_ERROR
    print(format_graph(config.package, graph))
    return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
