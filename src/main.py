"""Точка входа CLI: чтение XML и вывод строк ключ=значение."""

import argparse
import sys
from dataclasses import fields
from pathlib import Path
from typing import Optional, Sequence

from src.config import Config, load_config
from src.validation import ConfigError


SUCCESS = 0
CONFIG_ERROR = 2


def create_parser() -> argparse.ArgumentParser:
    """Создать CLI с опцией выбора XML-конфигурации."""
    parser = argparse.ArgumentParser(
        description="Практическая работа 2, вариант 30, этап 1."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        metavar="FILE",
        help="путь к XML-файлу со всеми шестью настройками",
    )
    return parser


def format_config(config: Config) -> str:
    """Представить все шесть настроек строками ключ=значение."""
    lines = []
    for field in fields(config):
        value = getattr(config, field.name)
        if isinstance(value, bool):
            value = str(value).lower()
        lines.append(f"{field.name}={value}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Вернуть 0 при успехе или 2 при ошибке конфигурации."""
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return CONFIG_ERROR
    print(format_config(config))
    return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
