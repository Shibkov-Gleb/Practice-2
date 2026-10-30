"""Точка входа CLI: чтение XML и вывод прямых зависимостей npm."""

__all__ = (
    "SUCCESS",
    "CONFIG_ERROR",
    "DEPENDENCY_ERROR",
    "create_parser",
    "format_dependencies",
    "main",
)

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.config import load_config
from src.npm import DependencyError, fetch_direct_dependencies
from src.validation import ConfigError


SUCCESS = 0
CONFIG_ERROR = 2
DEPENDENCY_ERROR = 1


def create_parser() -> argparse.ArgumentParser:
    """Создать CLI с опцией выбора XML-конфигурации."""
    parser = argparse.ArgumentParser(
        description="Практическая работа 2, вариант 30, этап 2."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        metavar="FILE",
        help="путь к XML-файлу со всеми шестью настройками",
    )
    return parser


def format_dependencies(package: str, dependencies: dict[str, str]) -> str:
    """Сформировать список прямых зависимостей с диапазонами версий."""
    if not dependencies:
        return f"У пакета {package} нет прямых зависимостей."
    lines = [f"Прямые зависимости пакета {package}:"]
    lines.extend(
        f"{name}: {specification}"
        for name, specification in sorted(dependencies.items())
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Получить зависимости и вернуть код результата."""
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return CONFIG_ERROR
    try:
        if config.test_mode:
            raise DependencyError(
                "test_mode: чтение тестового графа относится к этапу 3; "
                "для этапа 2 укажите false и URL реестра npm."
            )
        dependencies = fetch_direct_dependencies(
            config.repository, config.package
        )
    except DependencyError as error:
        print(f"Ошибка получения зависимостей: {error}", file=sys.stderr)
        return DEPENDENCY_ERROR
    print(format_dependencies(config.package, dependencies))
    return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
