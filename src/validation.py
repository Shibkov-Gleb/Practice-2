"""Проверка пользовательских параметров без сетевых запросов."""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit


PACKAGE_PATTERN = re.compile(
    r"(?:@[A-Za-z0-9][A-Za-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]*"
)
HOST_PATTERN = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?|[A-Fa-f0-9:]*:[A-Fa-f0-9:]+"
)
BOOLEAN_VALUES = {"true": True, "false": False}
ALLOWED_SCHEMES = {"http", "https"}
IMAGE_SUFFIX = ".svg"


class ConfigError(ValueError):
    """Ошибка чтения или проверки конфигурации."""


def validate_package(value: str) -> str:
    """Проверить простое либо scoped-имя пакета без пробелов."""
    if not PACKAGE_PATTERN.fullmatch(value):
        raise ConfigError(
            "package: ожидается имя пакета, например express, @scope/name "
            "или A; допустимы латинские буквы, цифры, '.', '_' и '-'."
        )
    return value


def parse_boolean(value: str, name: str) -> bool:
    """Преобразовать строго true или false в логическое значение."""
    if value not in BOOLEAN_VALUES:
        raise ConfigError(f"{name}: допустимы только true или false.")
    return BOOLEAN_VALUES[value]


def resolve_path(value: str, base_path: Path) -> Path:
    """Разрешить путь относительно каталога XML-конфигурации."""
    path = Path(value)
    if not path.is_absolute():
        path = base_path / path
    return path.resolve()


def validate_repository(value: str, test_mode: bool, base_path: Path) -> str:
    """Проверить URL либо доступность файла в тестовом режиме."""
    if not value or not all(character.isprintable() for character in value):
        raise ConfigError("repository: требуется URL или путь к файлу.")
    if test_mode:
        _validate_test_file(value, base_path)
    else:
        _validate_url(value)
    return value


def _validate_url(value: str) -> None:
    """Проверить синтаксис HTTP(S)-адреса и диапазон порта."""
    if any(character.isspace() for character in value):
        raise ConfigError("repository: URL не должен содержать пробелы.")
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as error:
        message = f"repository: некорректный URL: {error}."
        raise ConfigError(message) from error
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise ConfigError("repository: требуется URL с http:// или https://.")
    if not HOST_PATTERN.fullmatch(parsed.hostname):
        raise ConfigError("repository: некорректное имя сервера.")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigError("repository: запрещены логин и пароль в URL.")


def _validate_test_file(value: str, base_path: Path) -> None:
    """Проверить, что тестовый репозиторий является читаемым файлом."""
    if "://" in value:
        raise ConfigError("repository: в test_mode требуется путь к файлу.")
    try:
        path = resolve_path(value, base_path)
        if not path.is_file():
            raise ConfigError("repository: тестовый файл не найден.")
        with path.open("rb"):
            pass
    except ConfigError:
        raise
    except (OSError, ValueError, RuntimeError) as error:
        message = f"repository: невозможно открыть файл: {error}"
        raise ConfigError(message) from error


def validate_output(value: str, base_path: Path) -> str:
    """Проверить имя SVG и каталог без создания изображения."""
    if not value or not all(character.isprintable() for character in value):
        raise ConfigError("output_file: требуется непустое имя SVG-файла.")
    try:
        path = resolve_path(value, base_path)
        if path.suffix.lower() != IMAGE_SUFFIX:
            raise ConfigError("требуется расширение .svg.")
        _validate_output_location(path)
    except (OSError, ValueError, RuntimeError) as error:
        message = f"output_file: недопустимый путь: {error}"
        raise ConfigError(message) from error
    return value


def _validate_output_location(path: Path) -> None:
    """Проверить доступность места сохранения будущего файла."""
    if not path.parent.is_dir():
        raise ConfigError("родительский каталог не существует.")
    if path.exists() and not path.is_file():
        raise ConfigError("путь указывает не на обычный файл.")
    target = path if path.exists() else path.parent
    if not os.access(target, os.W_OK):
        raise ConfigError("нет прав на запись.")


def validate_filter(value: str) -> str:
    """Разрешить пустой фильтр или печатную подстроку в одной строке."""
    if not all(character.isprintable() for character in value):
        raise ConfigError("filter_substring: запрещены управляющие символы.")
    return value
